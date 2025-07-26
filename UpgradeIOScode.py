from netmiko import ConnectHandler, file_transfer
from getUser import get_netmiko_creds
from pathlib import Path
import time
import datetime
import logging
 
 
class NetworkDevice:
   def __init__(self, ip, username, password, device_type='cisco_ios'):
       self.ip = ip
       self.username = username
       self.password = password
       self.device_type = device_type
       self.connection = None
 
   def connect(self):
       self.connection = ConnectHandler(
           device_type=self.device_type,
           ip=self.ip,
           username=self.username,
           password=self.password,
           session_timeout=60 * 10,    #  10 minutes
           fast_cli=False             # Ensure commands are executed sequentially
       )
       print(f"Connected to {self.ip}")
       logging.info(f"Connected to {self.ip}")
 
   def disconnect(self):
       if self.connection:
           self.connection.disconnect()
           print(f"Disconnected from {self.ip}")
           logging.info(f"Disconnected from {self.ip}")
          
   def enable_scp(self):
       if not self.connection:
           self.connect()
       self.connection.send_config_set(['ip scp server enable'])
       logging.info(f"SCP enabled on {self.ip}")
       print(f"SCP enabled on {self.ip}")
 
   def upload_firmware(self, local_file_path, remote_file_path):
       if not self.connection:
           self.connect()
       try:
           transfer_result = file_transfer(
               self.connection,
              source_file=str(local_file_path),
               dest_file=remote_file_path,
               file_system='flash:',
               overwrite_file=True
       )
           logging.info(f"IOS code upload result:  {transfer_result}")
           print(f"IOS code upload result:  {transfer_result}")
           return transfer_result
       except Exception as e:
           if "Administratively disabled" in str(e):
               logging.warning(f"SCP is disabled on {self.ip}, enabling SCP.")
               self.enable_scp()
               transfer_result = file_transfer(
                   self.connection,
                  source_file=str(local_file_path),
                   dest_file=remote_file_path,
                   file_system='flash:',
                   overwrite_file=True,
                   timeout=600  # 10 minutes timeout
               )
               logging.info(f"IOS upload result after enabling SCP: {transfer_result} ")
               return transfer_result
           else:
               logging.error(f"Failed to upload IOS properly:  {e}")
               raise
          
   def set_boot_image(self, remote_file_path):
       if not self.connection:
           self.connect()
       boot_command = f"boot system flash:{remote_file_path}"
      self.connection.send_config_set([boot_command])
       logging.info(f"boot image set to {remote_file_path} on {self.ip}")
       print(f"boot image set to {remote_file_path} on {self.ip}")
 
   def schedule_reload(self, reload_time):
       if not self.connection:
           self.connect()
       command = (f"reload at {reload_time}")
       logging.info(f"Sending reload command: {command}")
       output = self.connection.send_command(command, expect_string=r'\[confirm\]')
       logging.info(f"Intial reload command output:  {output}")
       output += self.connection.send_command("\n")
       print(f"Reload confirmation output: {output}")
       logging.info(f"Reload confirmation output: {output}")
       logging.info(f"DEVICE RELOAD  scheduled for {reload_time} on {self.ip}")
       print(f"DEVICE RELOAD  scheduled for {reload_time} on {self.ip}")
 
   def save_configuration(self):
       if not self.connection:
           self.connect()
       self.connection.save_config()
       logging.info(f"Configuration saved on {self.ip}")
       print(f"Configuration saved on {self.ip}")
 
def get_reload_time():
   while True:
       reload_time = input("Enter the reload time (HH:MM, 24-hour format): ")
       try:
           # Validate time format
           valid_time = datetime.datetime.strptime(reload_time, "%H:%M")
           current_time = datetime.datetime.now()
           if valid_time.time() <= current_time.time():
               raise ValueError("The reload time must be in the future.")
           break
       except ValueError as e:
           print(f"Invalid time format or time in the past. Please try again. Error: {e}")
   return reload_time
 
def setup_logging(log_directory, log_filename):
   log_path = log_directory / log_filename
   logging.basicConfig(
       filename=log_path,
       format='%(asctime)s %(levelname)s: %(message)s',
       filemode='a',
       datefmt='%Y-%m-%d %H:%M:%S',
       level=logging.INFO
   )
   logging.info(" Logging setup complete.")
 
def main():
   # Get our logging in order
   LOGdirectory = Path('E:\\scripts\\dwilson\\')
   log_filename = "UpgradeCode.log"
   setup_logging(LOGdirectory, log_filename)
 
   # Get your user and password
   netmikoUser,passwd = get_netmiko_creds()
 
   # Define your device
   ip = input(" Enter the device IP address: ")
   device = NetworkDevice(ip=ip, username=netmikoUser, password=passwd)
  
   # set logging on 
   #setup_logging
 
   # Connect to the device
   device.connect()
 
   # Upload the firmware
   local_file_path = Path('E:\\tftp\\cat9k_iosxe.17.06.03.SPA.bin')
   remote_file_path = 'cat9k_iosxe.17.06.03.SPA.bin'
   logging.info("beginning file transfer")
   print("begnining file transfer")
   upload_result = device.upload_firmware(local_file_path, remote_file_path)
   if upload_result['file_exists']:
       print("IOS Code uploaded successfully.")
       logging.info("IOS Code uploaded successfully")
   else:
       print("IOS Code upload failed.")
       logging.info("IOS Code upload failed.")
       device.disconnect()
       return
 
   # Set the boot image
   device.set_boot_image(remote_file_path)
   print("Boot image set successfully.")
   logging.info("Boot image set successfully.")
 
   # Save the configuration
   device.save_configuration()
   print("Config saved successfully.")
   logging.info("Config saved successfully.")
 
   # Schedule the reload
   reload_time = get_reload_time()
   device.schedule_reload(reload_time)
   print(f"Reload scheduled at {reload_time}.")
   logging.info(f"Reload scheduled at {reload_time}.")
 
   # Disconnect from the device
   device.disconnect()
   print("Disconnected from the device.")
   logging.info("Disconnected from the device.")
 
if __name__ == "__main__":
   main()
