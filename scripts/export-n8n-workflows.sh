#!/bin/bash
set -e

# Configuration
REPO_DIR="/home/recog/recognition-workbench"
DATE_DIR=$(date '+%Y-%m-%d')
WORKFLOWS_DIR="$REPO_DIR/workflows/$DATE_DIR"

echo "🔄 Exporting ALL n8n workflows..."
echo "📁 Target: workflows/$DATE_DIR"

# Create workflows directory
mkdir -p "$WORKFLOWS_DIR"

# Export all workflows to a single file in container
docker exec n8n n8n export:workflow --all --output=/tmp/workflows-export.json

# Copy exported file to host
docker cp n8n:/tmp/workflows-export.json /tmp/

# Parse the export file and split into individual workflow files
echo "🔍 Parsing workflows..."
python3 << EOF
import json
import os

export_file = '/tmp/workflows-export.json'
output_dir = '$WORKFLOWS_DIR'
os.makedirs(output_dir, exist_ok=True)

# Read the export file
with open(export_file, 'r') as f:
    content = f.read().strip()

# Try parsing as JSON array first
try:
    workflows = json.loads(content)
    if not isinstance(workflows, list):
        workflows = [workflows]
except:
    # Try newline-delimited JSON
    workflows = []
    for line in content.split('\n'):
        if line.strip():
            try:
                workflows.append(json.loads(line))
            except:
                pass

total_count = 0
active_count = 0
for wf in workflows:
    name = wf.get('name', 'unnamed').replace(' ', '_').replace('/', '-')
    status = "✅ ACTIVE" if wf.get('active', False) else "⏭️  inactive"
    filename = f"{output_dir}/{name}.json"
    
    with open(filename, 'w') as f:
        json.dump(wf, f, indent=2)
    
    print(f"  {status}: {name}.json")
    total_count += 1
    if wf.get('active', False):
        active_count += 1

print(f"\n📊 Summary: {total_count} total, {active_count} active workflows saved to workflows/$DATE_DIR")
EOF

# Clean up temp files
rm -f /tmp/workflows-export.json
docker exec n8n rm -f /tmp/workflows-export.json

WORKFLOW_COUNT=$(ls -1 "$WORKFLOWS_DIR"/*.json 2>/dev/null | wc -l)

if [ $WORKFLOW_COUNT -eq 0 ]; then
    echo "⚠️  No workflows found"
    rmdir "$WORKFLOWS_DIR" 2>/dev/null || true
    exit 1
fi

# Git operations
cd "$REPO_DIR"

# Add all workflows
git add workflows/

# Check if there are changes
if git diff --staged --quiet; then
    echo "✅ No changes to commit (workflows unchanged)"
else
    # Show what changed
    echo "📝 Changes:"
    git diff --staged --name-status
    
    # Commit
    git commit -m "Export n8n workflows - $DATE_DIR"
    
    echo "✅ Changes committed"
    echo ""
    echo "📤 To push, run: git push -u origin main"
fi

echo "🎉 Done!"
