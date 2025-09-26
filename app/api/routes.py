"""
API路由定义
"""
import os
import hashlib
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from app.models.task import (
    TaskCreateRequest, TaskResponse, TaskDetailResponse, 
    AnalysisResultResponse, AnalysisTask, TaskStatus
)
from app.core.config import get_settings
from app.core.security import verify_api_key_header
from fastapi import Header
from app.services.task_manager import task_manager
from app.services.file_handler import FileHandler
from loguru import logger

router = APIRouter(prefix="/api", tags=["API"])

# 初始化服务
file_handler = FileHandler()


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """验证API密钥（通过X-API-Key头）"""
    if not verify_api_key_header(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥"
        )
    return x_api_key


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "message": "VMware EDR 样本分析系统运行正常"}


@router.post("/analyze", response_model=TaskResponse)
async def submit_analysis(
    file: UploadFile = File(..., description="要分析的样本文件"),
    vm_names: Optional[str] = Form(None, description="虚拟机名称列表，用逗号分隔"),
    timeout: int = Form(300, description="分析超时时间（秒）"),
    api_key: str = Depends(verify_api_key)
):
    try:
        settings = get_settings()
        
        # 验证文件大小
        if file.size > settings.server.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制 ({settings.server.max_file_size} bytes)"
            )
        
        # 验证超时时间
        if timeout < 60 or timeout > settings.task_settings.max_analysis_timeout:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"超时时间必须在60到{settings.task_settings.max_analysis_timeout}秒之间"
            )
        
        # 处理虚拟机名称列表
        if vm_names:
            vm_list = [name.strip() for name in vm_names.split(",")]
            # 验证虚拟机名称
            available_vms = []
            if hasattr(settings, 'edr_analysis') and settings.edr_analysis:
                available_vms = [vm.name for vm in settings.edr_analysis.vms]
            invalid_vms = [vm for vm in vm_list if vm not in available_vms]
            if invalid_vms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的虚拟机名称: {', '.join(invalid_vms)}"
                )
        else:
            vm_list = []
            if hasattr(settings, 'edr_analysis') and settings.edr_analysis:
                vm_list = [vm.name for vm in settings.edr_analysis.vms]
        
        # 保存文件
        file_info = await file_handler.save_uploaded_file(file)

        # 创建分析任务
        task = AnalysisTask(
            file_name=file.filename,
            file_hash=file_info["hash"],
            file_size=file_info["size"],
            file_path=file_info["path"],
            is_compressed=file_info.get("is_compressed", False),
            vm_names=vm_list,
            timeout=timeout
        )
        
        # 提交任务
        await task_manager.submit_task(task)
        
        logger.info(f"任务已创建: {task.task_id}, 文件: {file.filename}")
        
        return TaskResponse(
            task_id=task.task_id,
            status=task.status,
            message="任务已成功提交，正在处理中"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交分析任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交任务失败: {str(e)}"
        )


@router.get("/task/{task_id}", response_model=TaskDetailResponse)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    查询任务状态
    
    Args:
        task_id: 任务ID
        api_key: API密钥
    
    Returns:
        TaskDetailResponse: 任务详情
    """
    try:
        task = await task_manager.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        return TaskDetailResponse(**task.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务失败: {str(e)}"
        )


@router.get("/result/{task_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    获取分析结果
    
    Args:
        task_id: 任务ID
        api_key: API密钥
    
    Returns:
        AnalysisResultResponse: 分析结果
    """
    try:
        task = await task_manager.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务尚未完成"
            )
        
        # 统计告警数量
        total_alerts = sum(len(vm_result.alerts) for vm_result in task.vm_results)
        
        # 生成摘要
        summary = {
            "total_vms": len(task.vm_results),
            "successful_vms": len([r for r in task.vm_results if r.status == "completed"]),
            "failed_vms": len([r for r in task.vm_results if r.status == "failed"]),
            "analysis_duration": (
                (task.completed_at - task.started_at).total_seconds() 
                if task.started_at and task.completed_at else None
            )
        }
        
        return AnalysisResultResponse(
            task_id=task.task_id,
            status=task.status,
            total_alerts=total_alerts,
            vm_results=task.vm_results,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析结果失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取结果失败: {str(e)}"
        )


@router.get("/tasks", response_model=List[TaskDetailResponse])
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    """
    获取任务列表
    
    Args:
        status: 任务状态过滤
        limit: 返回数量限制
        api_key: API密钥
    
    Returns:
        List[TaskDetailResponse]: 任务列表
    """
    try:
        tasks = await task_manager.list_tasks(status=status, limit=limit)
        return [TaskDetailResponse(**task.dict()) for task in tasks]
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}"
        )


@router.delete("/task/{task_id}")
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    取消任务

    Args:
        task_id: 任务ID
        api_key: API密钥

    Returns:
        dict: 操作结果
    """
    try:
        success = await task_manager.cancel_task(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无法取消"
            )

        return {"message": "任务已取消"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消任务失败: {str(e)}"
        )


@router.get("/queue/status")
async def get_queue_status(
    api_key: str = Depends(verify_api_key)
):
    """
    获取队列状态

    Args:
        api_key: API密钥

    Returns:
        dict: 队列状态信息
    """
    try:
        status_info = await task_manager.get_queue_status()
        return status_info

    except Exception as e:
        logger.error(f"获取队列状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取队列状态失败: {str(e)}"
        )
