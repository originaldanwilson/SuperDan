#!/usr/bin/env python3
import requests
import csv
import os
import logging
import mysql.connector
from datetime import datetime
from tools import getScriptName, setupLogging, outputFilename   # your standard utilities

# === CONFIG ===
TRANCE_URL = "https://tranco-list.eu/top-1k.csv"
CSV_DIR = "F:\\scripts\\reports\\"          # adjust as needed
DB_NAME = "devices"
TABLE_NAME = "top_domains"

def downloadTrancoTop1k():
    logging.info("Downloading Tranco Top 1K list...")
    resp = requests.get(TRANCE_URL, timeout=15)
    resp.raise_for_status()
    return resp.text.splitlines()

def saveCsv(domains, csvFile):
    with open(csvFile, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "domain"])
        for line in domains:
            rank, domain = line.split(",")
            writer.writerow([rank, domain])
    logging.info(f"Saved CSV: {csvFile}")

def insertIntoMySQL(domains):
    try:
        from getCreds import get_firewall_creds
        netmikoUser, passwd, _ = get_firewall_creds()
        db = mysql.connector.connect(
            host="localhost",
            user=netmikoUser,
            password=passwd,
            database=DB_NAME
        )
        cur = db.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rank INT,
                domain VARCHAR(255),
                date_added DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.executemany(
            f"INSERT INTO {TABLE_NAME} (rank, domain) VALUES (%s, %s)",
            [tuple(line.split(",")) for line in domains]
        )
        db.commit()
        cur.close()
        db.close()
        logging.info(f"Inserted {len(domains)} domains into MySQL table '{TABLE_NAME}'")
    except Exception as e:
        logging.error(f"MySQL insert failed: {e}")

def main():
    scriptName = getScriptName()
    logFile = setupLogging(scriptName)
    logging.info(f"Script started: {scriptName}")

    try:
        domains = downloadTrancoTop1k()
        csvFile = os.path.join(CSV_DIR, outputFilename(scriptName, "csv"))
        saveCsv(domains, csvFile)
        insertIntoMySQL(domains)
    except Exception as e:
        logging.error(f"Error: {e}")

    logging.info("Script completed successfully.")

if __name__ == "__main__":
    main()
