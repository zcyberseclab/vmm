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
from app.services.vm_pool_manager import get_vm_pool_manager
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
        
        # VM选择将在文件保存后通过自动检测完成
        
        # 保存文件
        file_info = await file_handler.save_uploaded_file(file)

        # 自动检测样本类型和架构
        vm_list = await _auto_detect_and_select_vms(file_info["path"], vm_names, settings)

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
        edr_alerts = sum(len(vm_result.alerts) for vm_result in task.edr_results)
        behavior_events = len(task.behavior_results.events) if task.behavior_results else 0
        total_alerts = edr_alerts + behavior_events

        # 生成摘要 - 包含Sysmon分析在VM统计中
        edr_successful = len([r for r in task.edr_results if r.status == "completed"])
        edr_failed = len([r for r in task.edr_results if r.status == "failed"])

        # 统计Sysmon分析状态
        sysmon_successful = 0
        sysmon_failed = 0
        if task.behavior_results:
            if task.behavior_results.status == "completed":
                sysmon_successful = 1
            else:
                sysmon_failed = 1

        summary = {
            "total_vms": len(task.edr_results) + (1 if task.behavior_results else 0),
            "successful_vms": edr_successful + sysmon_successful,
            "failed_vms": edr_failed + sysmon_failed,
            "edr_alerts": edr_alerts,
            "behavior_events": behavior_events,
            "analysis_duration": (
                (task.completed_at - task.started_at).total_seconds()
                if task.started_at and task.completed_at else None
            )
        }

        return AnalysisResultResponse(
            task_id=task.task_id,
            status=task.status,
            total_alerts=total_alerts,
            edr_results=task.edr_results,
            behavior_results=task.behavior_results,
            analysis_metadata=task.analysis_metadata or {},
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


@router.get("/vm-pool/status")
async def get_vm_pool_status(api_key: str = Depends(verify_api_key)):
    """
    获取虚拟机资源池状态

    Returns:
        dict: VM资源池状态信息，包括各VM状态、性能统计等
    """
    try:
        vm_pool_manager = await get_vm_pool_manager()
        pool_status = await vm_pool_manager.get_pool_status()

        return {
            "status": "success",
            "data": pool_status,
            "message": "VM资源池状态获取成功"
        }

    except Exception as e:
        logger.error(f"获取VM资源池状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取VM资源池状态失败: {str(e)}"
        )


@router.post("/vm-pool/reset-errors")
async def reset_vm_errors(api_key: str = Depends(verify_api_key)):
    """
    重置所有VM的错误状态

    Returns:
        dict: 重置结果
    """
    try:
        vm_pool_manager = await get_vm_pool_manager()

        # 获取所有VM名称
        pool_status = await vm_pool_manager.get_pool_status()
        reset_count = 0

        for vm_name, vm_details in pool_status['vm_details'].items():
            if vm_details['state'] == 'error':
                await vm_pool_manager.reset_vm_error(vm_name)
                reset_count += 1

        return {
            "status": "success",
            "data": {
                "reset_count": reset_count,
                "message": f"已重置 {reset_count} 个VM的错误状态"
            }
        }

    except Exception as e:
        logger.error(f"重置VM错误状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置VM错误状态失败: {str(e)}"
        )


async def _auto_detect_and_select_vms(file_path: str, vm_names: Optional[str], settings) -> List[str]:
    """
    自动检测样本类型和架构，选择合适的虚拟机

    Args:
        file_path: 样本文件路径
        vm_names: 用户指定的VM名称（可选）
        settings: 系统配置

    Returns:
        List[str]: 选择的VM名称列表
    """
    try:
        # 如果用户明确指定了VM，验证并使用用户指定的VM
        if vm_names:
            # 收集所有可用的VM名称
            all_available_vms = []

            # Windows VMs
            if settings.windows and settings.windows.edr_analysis:
                all_available_vms.extend([vm.name for vm in settings.windows.edr_analysis.vms])

            # Linux VMs
            if settings.linux and settings.linux.behavioral_analysis:
                all_available_vms.extend([vm.name for vm in settings.linux.behavioral_analysis.vms])

            vm_list = [name.strip() for name in vm_names.split(",")]
            invalid_vms = [vm for vm in vm_list if vm not in all_available_vms]
            if invalid_vms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的虚拟机名称: {', '.join(invalid_vms)}"
                )

            logger.info(f"使用用户指定的VM: {vm_list}")
            return vm_list

        # 自动检测样本类型
        sample_type = _detect_sample_type(file_path)
        logger.info(f"检测到样本类型: {sample_type}")

        if sample_type == "elf":
            # Linux ELF样本 - 检测架构并选择对应的Linux VM
            from app.services.linux.multi_arch.arch_manager import ArchManager

            arch_manager = ArchManager()
            detected_arch = arch_manager.detect_file_architecture(file_path)

            if not detected_arch:
                logger.warning(f"无法检测ELF文件架构: {file_path}")
                return []  # 空列表表示Linux分析但架构未知

            logger.info(f"检测到ELF架构: {detected_arch}")

            # 查找匹配的Linux VM
            if settings.linux and settings.linux.behavioral_analysis:
                for vm_config in settings.linux.behavioral_analysis.vms:
                    if vm_config.architecture == detected_arch:
                        logger.info(f"选择Linux VM: {vm_config.name} ({detected_arch})")
                        return []  # 返回空列表表示Linux分析，任务管理器会处理

            logger.warning(f"没有找到适合 {detected_arch} 架构的Linux VM")
            return []

        elif sample_type in ["pe", "dll", "unknown"]:
            # Windows样本 - 使用所有Windows EDR VM
            if settings.windows and settings.windows.edr_analysis:
                vm_list = [vm.name for vm in settings.windows.edr_analysis.vms]
                logger.info(f"检测到Windows样本，使用所有EDR VM: {vm_list}")
                return vm_list
            else:
                logger.warning("没有配置Windows EDR VM")
                return []

        else:
            logger.warning(f"未知样本类型: {sample_type}")
            # 默认使用Windows分析
            if settings.windows and settings.windows.edr_analysis:
                vm_list = [vm.name for vm in settings.windows.edr_analysis.vms]
                logger.info(f"未知样本类型，默认使用Windows EDR VM: {vm_list}")
                return vm_list
            return []

    except Exception as e:
        logger.error(f"自动检测VM失败: {e}")
        # 发生错误时，默认使用Windows分析
        if settings.windows and settings.windows.edr_analysis:
            vm_list = [vm.name for vm in settings.windows.edr_analysis.vms]
            logger.info(f"检测失败，默认使用Windows EDR VM: {vm_list}")
            return vm_list
        return []


def _detect_sample_type(file_path: str) -> str:
    """
    检测样本文件类型

    Args:
        file_path: 文件路径

    Returns:
        str: 文件类型 ("elf", "pe", "dll", "unknown")
    """
    try:
        with open(file_path, 'rb') as f:
            # 读取文件头
            header = f.read(64)

            if len(header) < 4:
                return "unknown"

            # 检查ELF魔数
            if header[:4] == b'\x7fELF':
                return "elf"

            # 检查PE魔数
            if header[:2] == b'MZ':
                # 进一步检查是否为PE文件
                if len(header) >= 64:
                    # 读取PE头偏移
                    try:
                        pe_offset = int.from_bytes(header[60:64], byteorder='little')
                        if pe_offset < len(header):
                            return "pe"
                        else:
                            # 需要读取更多数据来确认PE头
                            f.seek(pe_offset)
                            pe_header = f.read(4)
                            if pe_header == b'PE\x00\x00':
                                return "pe"
                    except:
                        pass
                return "pe"  # 有MZ头，假设是PE文件

            return "unknown"

    except Exception as e:
        logger.error(f"检测文件类型失败: {file_path} - {e}")
        return "unknown"
