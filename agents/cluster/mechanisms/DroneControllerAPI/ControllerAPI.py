from DroneControllerAPI.UDP import UDP
from DroneControllerAPI.Messages import *
from DroneControllerAPI.DCException  import DCException
import time 

#For simple testing 
class ControllerAPI:

	def __init__(self, ctlr_ip, ctlr_port):
		

		self.ctlr = UDP()
		self.ctlr_addr = (ctlr_ip,ctlr_port)
		self.Seqno = 1


	def StartFollow(self,VerticalOffset,HorizontalOffset):
		
		sfreq = StartFollowReq(Seqno=self.Seqno,
				VerticalOffset=VerticalOffset,
				HorizontalOffset=HorizontalOffset)

		self.ctlr.send(self.ctlr_addr,sfreq)
		try:
			sfrepl = self.ctlr.recv()
		except Exception as e:
			raise DCException(f"Timeout")
			return
		if sfrepl.Seqno != self.Seqno:
			# print(f"error in sequence number: local {self.Seqno} received {sfrepl.Seqno}")
			raise DCException(f"SEQ_NUMBER_INCONSISTENCY Local {self.Seqno} Received {sfrepl.Seqno}")
		self.Seqno = self.Seqno + 1
		return sfrepl.StatusCode



	def StopFollow(self):
		
		sfreq = StopFollowReq(Seqno=self.Seqno)

		self.ctlr.send(self.ctlr_addr,sfreq)
		try:
			sfrepl = self.ctlr.recv()
		except Exception as e:
			raise DCException(f"Timeout")
			return

		if sfrepl.Seqno != self.Seqno:
			raise DCException(f"SEQ_NUMBER_INCONSISTENCY Local {self.Seqno} Received {sfrepl.Seqno}")
		self.Seqno = self.Seqno + 1

		return sfrepl.StatusCode


