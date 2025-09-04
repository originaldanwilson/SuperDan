# Windows PerfStack Solution (No Embedded Browsers)

This solution works around corporate restrictions on embedded browsers by using **existing system browsers** instead.

## 🎯 **Problem Solved**

Your Windows environment doesn't allow embedded browsers (Playwright, Selenium, etc.). This solution:
- ✅ Uses **existing system browsers** (Edge, Chrome, Firefox, IE)
- ✅ **No browser automation** - just opens URLs
- ✅ **Multiple output methods** - batch files, PowerShell scripts, shortcuts
- ✅ **Manual screenshot** - you control when to capture

## 📁 **Windows Files**

- **`perfstack_windows.py`** - Main Windows-compatible script
- **`perfstack_windows.bat`** - Interactive Windows batch wrapper
- Your existing scripts still work on Linux/Mac

## 🚀 **Quick Start Methods**

### **Method 1: Double-Click Batch File (Easiest)**
1. Double-click **`perfstack_windows.bat`**
2. Follow the prompts
3. Choose your preferred method
4. Browser opens automatically

### **Method 2: Command Line**
```cmd
REM Open directly in browser
python perfstack_windows.py --host router01 --interface Gi0/1 --open

REM Create reusable batch file
python perfstack_windows.py --host 10.1.1.1 --interface Po5 --batch

REM Create PowerShell script  
python perfstack_windows.py --host switch01 --interface Ethernet1/1 --powershell
```

### **Method 3: Copy URL Only**
```cmd
python perfstack_windows.py --host router01 --interface Gi0/1 --info-only
```

## 🛠️ **Windows Output Methods**

### **1. Direct Browser Opening (--open)**
- **What it does**: Opens URL directly in your default browser
- **Best for**: Quick, one-time screenshots
- **Requirements**: Any browser (Edge, Chrome, Firefox, IE)
```cmd
python perfstack_windows.py --host router01 --interface Gi0/1 --open --browser edge
```

### **2. Windows Batch File (--batch)**
- **What it creates**: `.bat` file you can double-click
- **Best for**: Repeated use, sharing with colleagues
- **Output**: `perfstack_router01_Gi0-1_20240904_143022.bat`
```cmd
python perfstack_windows.py --host 10.1.1.1 --interface Po25 --batch
```
Then double-click the `.bat` file anytime!

### **3. PowerShell Script (--powershell)**
- **What it creates**: `.ps1` PowerShell script
- **Best for**: Advanced users, automation
- **Output**: `perfstack_switch01_Ethernet1-1_20240904_143022.ps1`
```cmd
python perfstack_windows.py --host switch01 --interface Ethernet1/1 --powershell
```
Run with: `.\perfstack_switch01_Ethernet1-1_20240904_143022.ps1`

### **4. URL Shortcut File (--url-file)**
- **What it creates**: Windows `.url` shortcut
- **Best for**: Desktop shortcuts, quick access
- **Output**: Double-clickable shortcut file
```cmd
python perfstack_windows.py --host router02 --interface Gi1/1 --url-file
```

### **5. Text File Only (--info-only)**
- **What it creates**: Text file with URL and instructions
- **Best for**: Copy/paste, documentation
```cmd
python perfstack_windows.py --host core-switch --interface Po10 --info-only
```

## 📋 **Step-by-Step Process**

### **For Any Method:**
1. **Run the script** (choose your method above)
2. **Browser opens** to SolarWinds login page
3. **Log in normally** (SSO, username/password, whatever your org uses)
4. **PerfStack loads** with the correct device and time window
5. **Take screenshot** manually (Windows+Shift+S)
6. **Save screenshot** with descriptive name

### **Screenshot Shortcuts:**
- **Windows 10/11**: `Windows + Shift + S` (Snipping Tool)
- **Alt method**: `PrtScn` button, paste in Paint
- **Third-party**: Greenshot, LightShot, etc.

## 🔧 **Windows Installation**

### **Prerequisites:**
```cmd
REM Check Python is installed
python --version

REM Install required Python packages
pip install requests
```

### **Files You Need:**
1. `perfstack_windows.py` - Main script
2. `perfstack_windows.bat` - Batch wrapper (optional)
3. `tools.py` - Your credentials helper

## 💡 **Pro Tips for Windows**

### **Browser Preferences:**
```cmd
REM Force specific browser
python perfstack_windows.py --host router01 --interface Gi0/1 --open --browser edge
python perfstack_windows.py --host router01 --interface Gi0/1 --open --browser chrome
```

### **Time Windows:**
```cmd
REM Last 24 hours
python perfstack_windows.py --host switch01 --interface Po5 --hours 24 --batch

REM Last 30 days  
python perfstack_windows.py --host router01 --interface Gi0/1 --hours 720 --open
```

### **Batch Processing:**
Create a batch file for multiple devices:
```batch
@echo off
echo Generating PerfStack URLs for all core devices...

python perfstack_windows.py --host core-router-01 --interface Gi0/1 --batch
python perfstack_windows.py --host core-router-02 --interface Gi0/1 --batch
python perfstack_windows.py --host core-switch-01 --interface Po25 --batch
python perfstack_windows.py --host core-switch-02 --interface Po25 --batch

echo Done! Check the .bat files created.
pause
```

## 🛡️ **Corporate Environment Notes**

### **Firewall/Proxy:**
- Script uses your **existing Python requests** library
- **Same network access** as your other SolarWinds scripts
- **No special ports** or protocols required

### **Security:**
- **No browser automation** - just opens URLs
- **Uses existing authentication** - whatever your org requires
- **No credentials stored** in URLs or files
- **Manual control** - you decide when to authenticate and screenshot

### **Group Policy:**
- **No browser policies** affected - uses normal browsing
- **No installation** required - just Python scripts
- **No admin rights** needed

## 🔍 **Troubleshooting**

### **"Python not found"**
```cmd
REM Check Python installation
where python
python --version

REM If not found, add Python to PATH or use full path
C:\Python39\python.exe perfstack_windows.py --host router01 --interface Gi0/1
```

### **"Module not found"**
```cmd
REM Install missing modules
pip install requests urllib3
```

### **"Can't resolve host"**
- Check your `tools.py` file has correct credentials
- Verify SWIS server URL in the script
- Test SWIS connectivity manually

### **"No interface found"**
- Use exact interface names: `GigabitEthernet0/1` not `Gi0/1`
- Or try partial matches: script searches for interfaces containing your text
- Check device is monitored in SolarWinds

### **Browser doesn't open**
- Try different browser: `--browser chrome` or `--browser edge`
- Create batch file instead: `--batch` then double-click the `.bat` file
- Use URL shortcut: `--url-file` then double-click the `.url` file

## 📊 **Examples for Different Scenarios**

### **Quick Screenshot:**
```cmd
python perfstack_windows.py --host 10.1.1.1 --interface Po25 --open
```

### **Create Reusable Shortcuts:**
```cmd
REM For daily monitoring
python perfstack_windows.py --host core-router --interface Gi0/1 --hours 24 --batch

REM For weekly reports  
python perfstack_windows.py --host distribution-switch --interface Po10 --hours 168 --batch
```

### **Documentation/Sharing:**
```cmd
REM Get URL for email/tickets
python perfstack_windows.py --host problem-device --interface Ethernet1/1 --info-only

REM Create PowerShell for colleagues
python perfstack_windows.py --host shared-router --interface Gi1/1 --powershell
```

## 🎉 **Summary**

This Windows solution provides:

✅ **Corporate-friendly** - no embedded browsers  
✅ **Multiple methods** - batch files, PowerShell, shortcuts, direct opening  
✅ **Manual control** - you handle authentication and screenshots  
✅ **Reusable** - create files for repeated use  
✅ **Shareable** - send batch files to colleagues  

**Best workflow**: Use `--batch` to create reusable `.bat` files for devices you monitor regularly!
