#!/bin/bash
# 简单的VirtualBox安装脚本
# 使用方法: sudo bash install_vbox.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 VirtualBox安装脚本${NC}"
echo "=================================="

# 检查是否为root用户
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}❌ 请使用root权限运行此脚本${NC}"
   echo "使用: sudo bash install_vbox.sh"
   exit 1
fi

# 检查是否为Ubuntu系统
if ! command -v lsb_release &> /dev/null; then
    echo -e "${RED}❌ 此脚本仅支持Ubuntu系统${NC}"
    exit 1
fi

# 检查VirtualBox是否已安装
if command -v vboxmanage &> /dev/null; then
    VERSION=$(vboxmanage --version)
    echo -e "${GREEN}✅ VirtualBox已安装: $VERSION${NC}"
    echo "跳过安装步骤"
else
    echo -e "${YELLOW}❌ VirtualBox未安装，开始安装...${NC}"
    
    # 获取Ubuntu代号
    CODENAME=$(lsb_release -cs)
    echo -e "${GREEN}检测到Ubuntu代号: $CODENAME${NC}"
    
    # 更新包列表
    echo -e "${GREEN}🔧 更新包列表...${NC}"
    apt update
    
    # 安装基础依赖
    echo -e "${GREEN}🔧 安装基础依赖...${NC}"
    apt install -y wget gnupg lsb-release
    
    # 添加VirtualBox官方GPG密钥
    echo -e "${GREEN}🔧 添加VirtualBox GPG密钥...${NC}"
    wget -q https://www.virtualbox.org/download/oracle_vbox_2016.asc -O- | apt-key add -
    
    # 添加VirtualBox源
    echo -e "${GREEN}🔧 添加VirtualBox软件源...${NC}"
    echo "deb [arch=amd64] https://download.virtualbox.org/virtualbox/debian $CODENAME contrib" > /etc/apt/sources.list.d/virtualbox.list
    
    # 更新包列表
    echo -e "${GREEN}🔧 更新包列表...${NC}"
    apt update
    
    # 安装VirtualBox
    echo -e "${GREEN}🔧 安装VirtualBox 7.0...${NC}"
    apt install -y virtualbox-7.0
    
    echo -e "${GREEN}✅ VirtualBox安装完成${NC}"
fi

# 设置用户权限
echo -e "${GREEN}🔧 设置用户权限...${NC}"

# 检查是否有vmm用户，没有则创建
if ! id "vmm" &>/dev/null; then
    echo -e "${GREEN}创建用户: vmm${NC}"
    useradd -m -s /bin/bash vmm
    echo "vmm:vmm123" | chpasswd
    echo -e "${GREEN}用户vmm创建完成，密码: vmm123${NC}"
else
    echo -e "${GREEN}用户vmm已存在${NC}"
fi

# 添加用户到vboxusers组
usermod -aG vboxusers vmm
echo -e "${GREEN}✅ 用户vmm已添加到vboxusers组${NC}"

# 创建虚拟机目录
echo -e "${GREEN}🔧 创建虚拟机目录...${NC}"
mkdir -p /home/vmm/VirtualBox\ VMs
mkdir -p /home/vmm/vmm-vms
mkdir -p /home/vmm/.config/VirtualBox
chown -R vmm:vmm /home/vmm/

# 测试VirtualBox安装
echo -e "${GREEN}🧪 测试VirtualBox安装...${NC}"
if su - vmm -c "vboxmanage --version" &>/dev/null; then
    VERSION=$(su - vmm -c "vboxmanage --version")
    echo -e "${GREEN}✅ VirtualBox测试成功: $VERSION${NC}"
    
    # 显示当前虚拟机列表
    VM_LIST=$(su - vmm -c "vboxmanage list vms" 2>/dev/null || echo "")
    if [[ -n "$VM_LIST" ]]; then
        echo -e "${GREEN}当前虚拟机列表:${NC}"
        echo "$VM_LIST"
    else
        echo -e "${YELLOW}当前没有虚拟机${NC}"
    fi
else
    echo -e "${RED}❌ VirtualBox测试失败${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 VirtualBox安装和配置完成！${NC}"
echo "=================================="
echo -e "${GREEN}后续步骤:${NC}"
echo "1. 切换到vmm用户: su - vmm"
echo "2. 测试命令: vboxmanage --version"
echo "3. 导入虚拟机: vboxmanage import your-vm.ova"
echo "4. 启动虚拟机: vboxmanage startvm <vm-name> --type headless"
echo "5. 查看虚拟机: vboxmanage list vms"
echo ""
echo -e "${GREEN}常用命令:${NC}"
echo "- 列出所有虚拟机: vboxmanage list vms"
echo "- 查看运行中的虚拟机: vboxmanage list runningvms"
echo "- 关闭虚拟机: vboxmanage controlvm <vm-name> poweroff"
echo "- 创建快照: vboxmanage snapshot <vm-name> take clean"
echo "- 恢复快照: vboxmanage snapshot <vm-name> restore clean"
echo "=================================="
