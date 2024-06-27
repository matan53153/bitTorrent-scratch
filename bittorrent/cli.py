import argparse
import asyncio
import signal
import logging

from concurrent.futures import CancelledError

from torrent import Torrent
from client import TorrentClient