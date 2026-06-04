#!/usr/bin/env bash
# Instala v4l2loopback en Amazon Linux 2023 (kernel 6.1) y crea /dev/video0 virtual.
# Ejecutar UNA sola vez en el host EC2 antes de levantar docker-compose.
#
# Uso:
#   chmod +x setup_camera_ec2.sh
#   sudo ./setup_camera_ec2.sh

set -euo pipefail

KERNEL=$(uname -r)
echo "[1/5] Kernel detectado: $KERNEL"

echo "[2/5] Instalando dependencias..."
dnf install -y kernel-devel-"$KERNEL" dkms git make gcc

echo "[3/5] Clonando y compilando v4l2loopback..."
TMPDIR=$(mktemp -d)
git clone --depth=1 https://github.com/umlaeute/v4l2loopback.git "$TMPDIR/v4l2loopback"
cd "$TMPDIR/v4l2loopback"
make
make install
cd /
rm -rf "$TMPDIR"

echo "[4/5] Cargando módulo..."
modprobe v4l2loopback devices=1 video_nr=0 card_label="VirtualCam" exclusive_caps=1

# Permisos de lectura/escritura para todos (necesario para los containers Docker)
chmod 666 /dev/video0
echo "  /dev/video0 creado: $(ls -la /dev/video0)"

echo "[5/5] Persistiendo configuración al arranque..."
echo "v4l2loopback" > /etc/modules-load.d/v4l2loopback.conf
cat > /etc/modprobe.d/v4l2loopback.conf << 'EOF'
options v4l2loopback devices=1 video_nr=0 card_label="VirtualCam" exclusive_caps=1
EOF

# udev rule para restaurar permisos tras cada boot
cat > /etc/udev/rules.d/99-v4l2loopback.rules << 'EOF'
KERNEL=="video0", SUBSYSTEM=="video4linux", MODE="0666"
EOF

echo ""
echo "Listo. /dev/video0 disponible. Ahora ejecuta: sudo docker-compose up -d"
