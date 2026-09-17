# -*- coding: utf-8 -*-
"""SQLite 去重与留痕。同一个仓库/评论不重复入库，且保留首见时间以便做速度曲线。"""
import os
import sqlite3
import time

DDL = """
CREATE TABLE IF NOT EXISTS seen (
    source_id   TEXT PRIMARY KEY,
    source      TEXT,
    url         TEXT,
    title       TEXT,
    first_seen  INTEGER,
    last_seen   INTEGER,
    times_seen  INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT,
    stars_total INTEGER,
    stars_window INTEGER,
    forks       INTEGER,
    ts          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_hist ON history(source_id, ts);
"""


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.c = sqlite3.connect(path)
        self.c.executescript(DDL)
        self.c.commit()

    def split_new(self, records, cooldown_days=7):
        """返回 (待处理记录, 冷却期内跳过数)。

        去重不是"见过就永久丢弃"，否则日更流水线第二天会拿到空列表。
        正确做法是冷却期：同一对象在 N 天内不重复评估，之后允许重新评估
        （因为它的 star 曲线、issue 讨论都在变化，值得重看）。
        """
        out, skipped = [], 0
        now = int(time.time())
        cut = now - int(cooldown_days * 86400)
        for r in records:
            sid = r.get("source_id")
            if not sid:
                continue
            row = self.c.execute(
                "SELECT first_seen FROM seen WHERE source_id=?", (sid,)).fetchone()
            if row and row[0] >= cut:
                skipped += 1
                self.c.execute(
                    "UPDATE seen SET last_seen=?, times_seen=times_seen+1 WHERE source_id=?",
                    (now, sid))
            else:
                out.append(r)
                if row:
                    self.c.execute(
                        "UPDATE seen SET last_seen=?, times_seen=times_seen+1 WHERE source_id=?",
                        (now, sid))
                else:
                    self.c.execute(
                        "INSERT INTO seen(source_id,source,url,title,first_seen,last_seen)"
                        " VALUES(?,?,?,?,?,?)",
                        (sid, r.get("source"), r.get("url"), r.get("title"), now, now))
            if r.get("stars_total"):
                self.c.execute(
                    "INSERT INTO history(source_id,stars_total,stars_window,forks,ts)"
                    " VALUES(?,?,?,?,?)",
                    (sid, r.get("stars_total"), r.get("stars_window"),
                     r.get("forks"), now))
        self.c.commit()
        return out, skipped

    def close(self):
        self.c.close()
