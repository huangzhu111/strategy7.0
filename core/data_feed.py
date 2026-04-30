"""
数据供给模块
"""
import os
import sqlite3
import tempfile
import pandas as pd
from datetime import datetime
from typing import Optional

try:
    import paramiko
except ImportError:
    paramiko = None


class ContractCalendar:
    """合约日历"""
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.roll_dates = []

    def detect_roll_dates(self):
        self.df["contract_next"] = self.df["current_contract"].shift(-1)
        self.df["is_roll_date"] = (self.df["current_contract"] != self.df["contract_next"]) & self.df["contract_next"].notna()
        self.roll_dates = self.df[self.df["is_roll_date"]].index.tolist()
        return self.roll_dates

    def is_roll_date(self, dt: datetime) -> bool:
        return dt in self.roll_dates

    def get_next_contract(self, current_contract: str) -> Optional[str]:
        idx = self.df[self.df["current_contract"] == current_contract].index
        if len(idx) > 0:
            pos = self.df.index.get_loc(idx[0])
            if pos + 1 < len(self.df):
                return self.df.iloc[pos + 1]["current_contract"]
        return None


class FuturesDataFeed:
    """期货数据供给"""
    def __init__(self, db_path=None, table_name="m1_daily_ohlc", use_remote=False,
                 vps_host=None, vps_port=22, vps_username=None, vps_db_path=None):
        self.db_path = db_path
        self.table_name = table_name
        self.use_remote = use_remote
        self.vps_host = vps_host
        self.vps_port = vps_port
        self.vps_username = vps_username
        self.vps_db_path = vps_db_path
        self.df = None
        self.calendar = None

    @classmethod
    def from_config(cls, config):
        return cls(
            db_path=config.db_path, table_name=config.table_name,
            use_remote=getattr(config, "use_remote", False),
            vps_host=getattr(config, "vps_host", None),
            vps_port=getattr(config, "vps_port", 22),
            vps_username=getattr(config, "vps_username", None),
            vps_db_path=getattr(config, "vps_db_path", None),
        )

    def _find_ssh_key(self) -> str:
        for path in [
            os.path.expanduser("~/.ssh/id_rsa"),
            os.path.expanduser("~/.ssh/id_ed25519"),
            os.path.expanduser("~/.ssh/id_ecdsa"),
        ]:
            if os.path.exists(path):
                return path
        return None

    def _connect_remote(self) -> sqlite3.Connection:
        if paramiko is None:
            raise Exception("请安装 paramiko: pip install paramiko")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_path = self._find_ssh_key()
        if key_path:
            try:
                key = paramiko.RSAKey.from_private_key_file(key_path)
                ssh.connect(self.vps_host, port=self.vps_port, username=self.vps_username, pkey=key)
            except Exception:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    ssh.connect(self.vps_host, port=self.vps_port, username=self.vps_username, pkey=key)
                except Exception:
                    ssh.connect(self.vps_host, port=self.vps_port, username=self.vps_username,
                                look_for_keys=True, allow_agent=True)
        else:
            ssh.connect(self.vps_host, port=self.vps_port, username=self.vps_username,
                        look_for_keys=True, allow_agent=True)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_path = tmp.name
        tmp.close()
        sftp = ssh.open_sftp()
        sftp.get(self.vps_db_path, tmp_path)
        sftp.close()
        ssh.close()
        return sqlite3.connect(tmp_path)

    def load_data(self, from_date=None, to_date=None) -> pd.DataFrame:
        try:
            conn = self._connect_remote() if self.use_remote else sqlite3.connect(self.db_path)
            query = f"""
            SELECT date as datetime, open, high, low, close,
                   cape_index as 'index', volume, current_contract
            FROM {self.table_name} WHERE 1=1
            """
            if from_date:
                query += f" AND date >= '{from_date}'"
            if to_date:
                query += f" AND date <= '{to_date}'"
            query += " ORDER BY date"
            df = pd.read_sql(query, conn)
            conn.close()
            df = df.dropna(subset=["open", "high", "low", "close", "index"])
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            # 合约变更检测
            df["contract_next"] = df["current_contract"].shift(-1)
            df["current_contract_flag"] = (df["current_contract"] != df["contract_next"]).astype(int)
            df.drop(columns=["contract_next"], inplace=True)
            self.df = df
            self.calendar = ContractCalendar(df)
            self.calendar.detect_roll_dates()
            return df
        except Exception as e:
            print(f"数据加载错误: {e}")
            return None

    def is_roll_date(self, dt) -> bool:
        return self.calendar.is_roll_date(dt) if self.calendar else False
