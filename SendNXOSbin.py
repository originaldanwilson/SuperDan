import os
from datetime import datetime
from netmiko import ConnectHandler, SCPConn
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException
from getCreds import get_netmiko_creds
from tools import getScriptName, setupLogging, outputFilename
from openpyxl import Workbook

def upload_file_to_switch(switch, filePath, username, password, logging):
    result = {"switch": switch, "file": os.path.basename(filePath), "status": "Failure", "message": ""}
    try:
        logging.info(f"Connecting to {switch}...")
        conn = ConnectHandler(
            device_type='cisco_nxos',
            host=switch,
            username=username,
            password=password,
        )
        scp = SCPConn(conn)

        remote_path = f"bootflash:{os.path.basename(filePath)}"
        logging.info(f"Uploading {filePath} to {switch}:{remote_path}")
        scp.scp_transfer_file(filePath, remote_path)
        scp.close()

        logging.info(f"Upload complete for {switch}")
        result["status"] = "Success"
    except FileNotFoundError:
        msg = f"Local file not found: {filePath}"
        logging.error(msg)
        result["message"] = msg
    except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
        msg = f"Connection failed to {switch}: {str(e)}"
        logging.error(msg)
        result["message"] = msg
    except Exception as e:
        msg = f"Unexpected error for {switch}: {str(e)}"
        logging.error(msg)
        result["message"] = msg
    finally:
        try:
            conn.disconnect()
        except:
            pass
    return result

def write_results_to_excel(results, excelFile):
    wb = Workbook()
    ws = wb.active
    ws.title = "scp_results"
    ws.append(["Switch", "File", "Status", "Message"])
    for row in results:
        ws.append([row["switch"], row["file"], row["status"], row.get("message", "")])
    wb.save(excelFile)

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    scriptName = getScriptName()
    logging = setupLogging(scriptName, timestamp)
    netmikoUser, passwd, enable = get_netmiko_creds()

    # Define your list of switches and image files here
    switchList = ["switch1", "switch2", "switch3"]
    imageFiles = ["nxos.bin"]  # You can expand this list as needed

    logging.info("Starting SCP upload process")
    results = []
    for switch in switchList:
        for image in imageFiles:
            result = upload_file_to_switch(switch, image, netmikoUser, passwd, logging)
            results.append(result)

    outputExcel = outputFilename(scriptName, timestamp, "xlsx")
    write_results_to_excel(results, outputExcel)
    logging.info(f"Upload process completed. Results written to {outputExcel}")

if __name__ == "__main__":
    main()
