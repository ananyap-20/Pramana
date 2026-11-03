"""Optional native disposable MongoDB for real persistence/restart/restore tests."""
from pathlib import Path
import os
import socket
import subprocess
import time

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure


class LocalMongo:
    def __init__(self, executable, directory):
        self.executable = str(Path(executable).resolve(strict=True))
        self.directory = directory
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        self.uri = f'mongodb://127.0.0.1:{self.port}'
        self.process = None

    def start(self):
        self.process = subprocess.Popen([self.executable, '--bind_ip', '127.0.0.1', '--port', str(self.port),
            '--dbpath', str(self.directory), '--logpath', str(self.directory / 'mongo.log'), '--logappend',
            '--wiredTigerCacheSizeGB', '0.25'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('Disposable MongoDB exited before readiness.')
            try:
                with MongoClient(self.uri, serverSelectionTimeoutMS=250) as client:
                    client.admin.command('ping')
                return
            except ConnectionFailure:
                time.sleep(.1)
        self.stop()
        raise RuntimeError('Disposable MongoDB did not become ready.')

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                with MongoClient(self.uri, serverSelectionTimeoutMS=1000) as client:
                    client.admin.command('shutdown', force=True)
            except (ConnectionFailure, OperationFailure):
                pass  # A successful shutdown disconnects its caller.
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def restart(self):
        self.stop()
        self.start()
