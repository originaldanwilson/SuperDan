"""
Gantt Chart Generator for Network Engineering NaC Transformation
Visualizes the migration from CLI/GUI to DevOps NaC using GitHub and Ansible
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np

# Define project phases and tasks
tasks = [
    # Phase 1: Assessment & Planning
    {"name": "Current State Assessment", "start": 0, "duration": 2, "phase": "Planning"},
    {"name": "Stakeholder Buy-in & Training Plan", "start": 1, "duration": 2, "phase": "Planning"},
    {"name": "Tool Selection & Architecture Design", "start": 2, "duration": 2, "phase": "Planning"},
    
    # Phase 2: Infrastructure Setup
    {"name": "GitHub Repository Setup", "start": 4, "duration": 1, "phase": "Infrastructure"},
    {"name": "GitHub Actions Configuration", "start": 5, "duration": 2, "phase": "Infrastructure"},
    {"name": "Ansible Control Node Setup", "start": 5, "duration": 2, "phase": "Infrastructure"},
    {"name": "Cisco NaC Collections Installation", "start": 7, "duration": 1, "phase": "Infrastructure"},
    
    # Phase 3: Development & Testing
    {"name": "YAML Template Development", "start": 8, "duration": 3, "phase": "Development"},
    {"name": "Ansible Playbook Creation", "start": 9, "duration": 3, "phase": "Development"},
    {"name": "CI/CD Pipeline Development", "start": 10, "duration": 2, "phase": "Development"},
    {"name": "Lab Environment Testing", "start": 12, "duration": 3, "phase": "Development"},
    
    # Phase 4: Pilot & Training
    {"name": "Team Training Sessions", "start": 14, "duration": 2, "phase": "Training"},
    {"name": "Pilot with Non-Critical Devices", "start": 15, "duration": 3, "phase": "Pilot"},
    {"name": "Documentation & Runbooks", "start": 16, "duration": 2, "phase": "Training"},
    
    # Phase 5: Production Rollout
    {"name": "Phased Production Migration", "start": 18, "duration": 4, "phase": "Production"},
    {"name": "Parallel Run (Old & New Methods)", "start": 19, "duration": 3, "phase": "Production"},
    {"name": "Monitoring & Optimization", "start": 22, "duration": 2, "phase": "Production"},
    
    # Phase 6: Closure
    {"name": "Legacy Process Decommission", "start": 24, "duration": 1, "phase": "Closure"},
    {"name": "Post-Implementation Review", "start": 25, "duration": 1, "phase": "Closure"},
]

# Define colors for each phase
phase_colors = {
    "Planning": "#3498db",
    "Infrastructure": "#e74c3c",
    "Development": "#2ecc71",
    "Training": "#f39c12",
    "Pilot": "#9b59b6",
    "Production": "#1abc9c",
    "Closure": "#34495e"
}

# Create figure
fig, ax = plt.subplots(figsize=(16, 10))

# Calculate start date (today)
start_date = datetime.now()

# Plot each task
y_pos = np.arange(len(tasks))
for i, task in enumerate(tasks):
    task_start = start_date + timedelta(weeks=task["start"])
    task_duration = timedelta(weeks=task["duration"])
    
    ax.barh(i, task_duration.days, left=task_start, height=0.6, 
            color=phase_colors[task["phase"]], alpha=0.8, edgecolor='black', linewidth=0.5)
    
    # Add task name inside or next to the bar
    task_end = task_start + task_duration
    mid_point = task_start + task_duration / 2
    ax.text(mid_point, i, task["name"], ha='center', va='center', 
            fontsize=9, fontweight='bold', color='white')

# Format x-axis as dates
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=45, ha='right')

# Labels and title
ax.set_yticks(y_pos)
ax.set_yticklabels([])
ax.set_xlabel('Timeline', fontsize=12, fontweight='bold')
ax.set_title('Network Engineering NaC Transformation Project\nCLI/GUI → DevOps (GitHub + Ansible + Cisco NaC)', 
             fontsize=16, fontweight='bold', pad=20)

# Add grid
ax.grid(axis='x', alpha=0.3, linestyle='--')

# Create legend
legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, edgecolor='black', label=phase) 
                   for phase, color in phase_colors.items()]
ax.legend(handles=legend_elements, loc='upper right', fontsize=10, title='Project Phases')

# Add project duration info
total_weeks = max(task["start"] + task["duration"] for task in tasks)
ax.text(0.02, 0.98, f'Total Duration: {total_weeks} weeks (~{total_weeks//4} months)', 
        transform=ax.transAxes, fontsize=11, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('C:\\Users\\danda\\nac_transformation_gantt.png', dpi=300, bbox_inches='tight')
print("Gantt chart saved as: C:\\Users\\danda\\nac_transformation_gantt.png")
plt.show()
