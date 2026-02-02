# Script to add NDFC Fabric Exporter to SuperDan repository
# Run this from the SuperDan root directory

Write-Host "Adding NDFC Fabric Exporter to SuperDan repository..." -ForegroundColor Cyan

# Change to SuperDan root
Set-Location C:\Users\danda\SuperDan

# Add all files in the ndfc-fabric-exporter directory
git add ndfc-fabric-exporter/

# Show what will be committed
Write-Host "`nFiles to be committed:" -ForegroundColor Yellow
git status

# Commit the changes
Write-Host "`nCommitting changes..." -ForegroundColor Cyan
git commit -m "Add NDFC Fabric Exporter tool

- Python tool to extract NDFC fabric configurations
- Generates Ansible-compatible YAML files
- Compatible with Python 3.13.2 and Ansible Core 2.18.8
- Includes CLI interface, validation, and examples

Co-Authored-By: Warp <agent@warp.dev>"

# Push to GitHub
Write-Host "`nPushing to GitHub..." -ForegroundColor Cyan
git push origin master

Write-Host "`nDone! Check your repo at: https://github.com/originalDanWilson/SuperDan" -ForegroundColor Green
