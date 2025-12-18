import socket
import threading
import logging
import logging.config
from struct import *
import time
from DroneControllerAPI.Messages import *
from dataclass_struct import STRUCT_TYPE, dataclass_struct

# from src.env import *


type_to_dataclass = {
		MsgTypes.TRACTOR_INFO.value:TractorInfo,
		MsgTypes.DRONE_STATUS.value:DroneStatus,
		MsgTypes.AP_SENSOR_INFO.value:AutopilotSensorInfo,
		MsgTypes.START_FOLLOW_REQ.value:StartFollowReq,
		MsgTypes.START_FOLLOW_RPL.value:StartFollowRpl,
		MsgTypes.STOP_FOLLOW_REQ.value:StopFollowReq,
		MsgTypes.STOP_FOLLOW_RPL.value:StopFollowRpl,
		MsgTypes.SET_REPORTING_RATE_REQ.value:SetReportingRateReq,
		MsgTypes.SET_REPORTING_RATE_RPL.value:SetReportingRateRpl
}

logger = logging.getLogger(__name__)

class UDP(object):


	def __init__(self,ip="",port=0):
		self.sock = socket.socket(socket.AF_INET,
								socket.SOCK_DGRAM)

		self.sock.bind((ip,port))

		self.ip, self.port = self.sock.getsockname()

		self.recv_handler = self.__dumy_handler

		# logger.info(f"UDP started at {self.ip}:{self.port}")

	def ServeForever(self):
		self.rcv_th = threading.Thread(target = self.__rcv_loop,
									daemon=True)
		self.rcv_th.start()

	def RegisterRecvHandler(self,handler):
		self.recv_handler = handler

	def __bin_to_dataclass(self,msg):
		header = msg[:4]
		mtype = unpack('>i',header)[0]

		obj = type_to_dataclass[mtype].instance_from_buffer(msg)		
		return obj

	def __rcv_loop(self):
		#return in blocking mode if recv was invoked before
		# self.sock.settimeout(0)
		while True:

			data , addr = self.sock.recvfrom(1024)
			#print(f"received message _rcv {data} from {addr}")
			obj = self.__bin_to_dataclass(data)
			self.recv_handler(addr,obj)


	def __dumy_handler(self,address,data):
		pass

	def recv(self):
		try:
			self.sock.settimeout(2)
			data , addr = self.sock.recvfrom(1024)
			# print(f"received message recv {data} from {addr}")
		except socket.timeout as e: 
			raise e

		obj = self.__bin_to_dataclass(data)
		return obj

	def send(self,address,data):
		self.sock.sendto(data.to_buffer(),address)







