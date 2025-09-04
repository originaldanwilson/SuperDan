# SolarWinds PerfStack SSO Solutions

This guide provides **multiple solutions** to fix SSO authentication issues with SolarWinds PerfStack automation.

## 🎯 **Problem Solved**

Your existing scripts have SSO authentication issues. These enhanced scripts provide **4 different methods** to handle SSO reliably:

1. **Persistent Browser Profile** (Most Reliable)
2. **State File Method** (Good for automation)
3. **CDP Attach** (Use existing browser)
4. **Manual Authentication** (Interactive setup)

## 📁 **Files Created**

- **`perfstack_sso_enhanced.py`** - Full-featured SSO handler
- **`perfstack_easy.py`** - Simple wrapper for easy usage
- **Your existing scripts** - Still available as alternatives

## 🚀 **Quick Start**

### **Method 1: Easy Interactive Mode**
```bash
python3 perfstack_easy.py
```
Then follow the prompts!

### **Method 2: Command Line**
```bash
# Using persistent profile (best for SSO)
python3 perfstack_easy.py router01 GigabitEthernet0/1 --method profile

# Using state file
python3 perfstack_easy.py 10.1.1.1 Po5 --method state --headed

# Manual authentication (first time)
python3 perfstack_easy.py switch01 Ethernet1/1 --method manual
```

## 🔧 **SSO Methods Explained**

### **1. Persistent Profile Method (Recommended)**
- **How it works**: Uses a dedicated browser profile directory
- **Best for**: SSO with Windows Authentication/SAML
- **Pros**: Most reliable, handles complex SSO flows
- **Cons**: Takes more disk space
- **Usage**:
```bash
python3 perfstack_sso_enhanced.py --host router01 --interface Gi0/1 --profile ./browser_profile
```

### **2. State File Method**
- **How it works**: Saves cookies and session data to JSON file
- **Best for**: Simple SSO, automation scripts
- **Pros**: Lightweight, good for scripting
- **Cons**: May need re-authentication occasionally
- **Usage**:
```bash
python3 perfstack_sso_enhanced.py --host 10.1.1.1 --interface Po25 --state ~/.sw_state.json
```

### **3. CDP Attach Method**
- **How it works**: Connects to a browser you've already logged into
- **Best for**: When you want manual control of authentication
- **Pros**: Use any browser, full manual control
- **Cons**: Requires manual browser setup
- **Setup**:
```bash
# Start browser with remote debugging
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug

# Log into SolarWinds manually, then:
python3 perfstack_sso_enhanced.py --host router01 --interface Gi0/1 --cdp http://localhost:9222
```

### **4. Manual Authentication**
- **How it works**: Opens browser, waits for you to log in
- **Best for**: First-time setup, troubleshooting
- **Pros**: Full control, great for debugging
- **Cons**: Not fully automated
- **Usage**:
```bash
python3 perfstack_sso_enhanced.py --host switch01 --interface Ethernet1/1 --manual --headed
```

## 🛠️ **Installation Requirements**

```bash
# Install Playwright
pip install playwright

# Install browser binaries
playwright install chromium

# Optional: Install system browsers if not already installed
# Ubuntu/Debian:
sudo apt install chromium-browser microsoft-edge-stable

# Red Hat/CentOS:
sudo dnf install chromium microsoft-edge-stable
```

## 📊 **Features**

### **Enhanced Functionality**
- ✅ **Multiple SSO methods** - Choose what works best
- ✅ **Robust error handling** - Better error messages
- ✅ **Flexible authentication** - Works with various SSO providers
- ✅ **Chart wait logic** - Ensures charts are loaded before screenshot
- ✅ **Timestamped filenames** - No overwrites
- ✅ **Browser flexibility** - Chrome or Edge support

### **Smart Defaults**
- ✅ **Explicit time windows** - URL includes timeFrom/timeTo
- ✅ **SSL handling** - Ignores certificate errors
- ✅ **Viewport optimization** - 1600x900 for good screenshots
- ✅ **Network wait** - Waits for network idle before screenshot

## 🔧 **Troubleshooting**

### **SSO Still Not Working?**

1. **Try persistent profile method first**:
```bash
python3 perfstack_easy.py --method profile --headed
```

2. **Check your credentials function**:
```python
from tools import get_ad_creds
user, password = get_ad_creds()
print(f"Using: {user}")  # Verify correct username
```

3. **Test SWIS connection manually**:
```bash
curl -k -u "username:password" "https://orionApi.company.com:17774/SolarWinds/InformationService/v3/Json/Query?query=SELECT+TOP+1+NodeID+FROM+Orion.Nodes"
```

### **Browser Issues?**

1. **Clear browser data**:
```bash
rm -rf ~/.solarwinds_browser_profile
rm ~/.solarwinds_state.json
```

2. **Try different browser**:
```bash
python3 perfstack_sso_enhanced.py --host router01 --interface Gi0/1 --browser chrome --headed
```

3. **Check browser version**:
```bash
playwright install  # Update browser binaries
```

### **Network Issues?**

1. **Update URLs in script**:
   - Edit `DEFAULT_SWIS` and `DEFAULT_WEB` in the scripts
   - Make sure ports are correct (17774 for SWIS, 80/443 for web)

2. **Test connectivity**:
```bash
curl -k https://orion.company.com/Orion/Login.aspx
```

## 💡 **Pro Tips**

### **For Best SSO Experience**
1. **Start with persistent profile** - it handles most SSO scenarios
2. **Use headed mode first** - `--headed` lets you see what's happening
3. **Set up once, reuse** - profiles and state files are persistent
4. **Use IP addresses** - more reliable than hostnames for device lookup

### **For Automation**
1. **Use state file method** - lighter weight than profiles
2. **Include error handling** - check return codes in your scripts
3. **Add retries** - sometimes authentication needs a second attempt
4. **Monitor file sizes** - large screenshots might indicate loading issues

### **Command Line Examples**

```bash
# Quick test with visual feedback
python3 perfstack_easy.py router01 Gi0/1 --method profile --headed

# Production automation
python3 perfstack_easy.py 10.1.1.1 Po25 --method state --hours 24

# Troubleshooting
python3 perfstack_sso_enhanced.py --host problematic-device --interface Gi1/1 --manual --headed --browser chrome

# Batch processing (create a wrapper script)
for device in router01 router02 switch01; do
    python3 perfstack_easy.py $device Gi0/1 --method profile
done
```

## 🎉 **Summary**

Your SSO issues should now be resolved with these multiple approaches:

1. **Enhanced script** provides 4 different SSO methods
2. **Easy wrapper** makes it simple to use interactively  
3. **Robust error handling** gives better feedback
4. **Flexible authentication** works with various SSO providers

Start with the **persistent profile method** - it's the most reliable for complex SSO environments!
