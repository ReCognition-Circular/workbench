#!/bin/bash
echo "Organizing project structure..."

# Move docker-volumes if it exists in ubuntu
if [ -d "ubuntu/docker-volumes" ]; then
    echo "Moving docker-volumes..."
    mv ubuntu/docker-volumes ./
fi

# Remove empty ubuntu directory
if [ -d "ubuntu" ]; then
    echo "Removing ubuntu directory..."
    rmdir ubuntu 2>/dev/null || echo "ubuntu directory not empty, checking contents..."
    ls -la ubuntu/ 2>/dev/null || echo "ubuntu directory removed"
fi

# Create required directories
echo "Creating required directories..."
mkdir -p docker/{postgres,redis}
mkdir -p docker-volumes/{postgres-data,redis-data,media,static}
mkdir -p {backups,logs,scripts,docs/{api,deployment,user-guides}}

# Set permissions
echo "Setting permissions..."
chown -R 999:999 docker-volumes/postgres-data 2>/dev/null || true

# Clean up app directory (remove directories that should be at root)
echo "Cleaning app directory..."
rmdir app/backups 2>/dev/null || true
rmdir app/logs 2>/dev/null || true
rmdir app/scripts 2>/dev/null || true

# Final structure
echo "Final structure:"
tree -L 2
