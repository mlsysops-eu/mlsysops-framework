import struct
from dataclasses import dataclass, asdict, field
from dataclass_struct import STRUCT_TYPE, dataclass_struct
from enum import Enum


class MsgTypes(Enum):
	TRACTOR_INFO = 1
	DRONE_STATUS = 2
	AP_SENSOR_INFO = 3
	IN_POSITION = 4
	START_FOLLOW_REQ = 5
	START_FOLLOW_RPL = 6
	STOP_FOLLOW_REQ = 7
	STOP_FOLLOW_RPL = 8
	SET_REPORTING_RATE_REQ = 9
	SET_REPORTING_RATE_RPL = 10
	UAV_STATUS = 11
	DOME_VALUES_UPDATE = 12


@dataclass_struct
class Test:
	Type: int = field(default = MsgTypes.TRACTOR_INFO.value, metadata={STRUCT_TYPE:'>i'})
	param1: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	param2: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})


@dataclass
class UAVStatus:
	Type: int = MsgTypes.UAV_STATUS.value
	Status: int = 0


@dataclass_struct
class TractorInfo:
	Type: int = field(default = MsgTypes.TRACTOR_INFO.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	Timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	Longitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Latitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Altitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Heading: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Speed: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	DevID: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	lux_r: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_g: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_b: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_i: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	dome_timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>q'})


@dataclass_struct
class DroneStatus:
	Type: int = field(default = MsgTypes.DRONE_STATUS.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	Timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	State: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})


@dataclass_struct
class AutopilotSensorInfo:
	Type: int = field(default = MsgTypes.AP_SENSOR_INFO.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	Timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>q'})
	Longitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Latitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Altitude: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Heading: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Speed: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Pitch: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Roll: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	Yaw: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_r: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_g: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_b: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_i: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	dome_timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>q'})


@dataclass_struct
class StartFollowReq:
	Type: int = field(default = MsgTypes.START_FOLLOW_REQ.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	VerticalOffset: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	HorizontalOffset: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})

@dataclass_struct
class StartFollowRpl:
	Type: int = field(default = MsgTypes.START_FOLLOW_RPL.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	StatusCode: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})

@dataclass_struct
class StopFollowReq:
	Type: int = field(default = MsgTypes.STOP_FOLLOW_REQ.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})

@dataclass_struct
class StopFollowRpl:
	Type: int = field(default = MsgTypes.STOP_FOLLOW_RPL.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	StatusCode: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})


@dataclass_struct
class SetReportingRateReq:
	Type: int = field(default = MsgTypes.SET_REPORTING_RATE_REQ.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})

@dataclass_struct
class SetReportingRateRpl:
	Type: int = field(default = MsgTypes.SET_REPORTING_RATE_RPL.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	StatusCode: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})

#helper class 
@dataclass_struct
class DomeValuesUpdate:
	Type: int = field(default = MsgTypes.DOME_VALUES_UPDATE.value, metadata={STRUCT_TYPE:'>i'})
	Seqno: int = field(default = 0, metadata={STRUCT_TYPE:'>i'})
	lux_r: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_g: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_b: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	lux_i: float = field(default = 0, metadata={STRUCT_TYPE:'>f'})
	dome_timestamp: int = field(default = 0, metadata={STRUCT_TYPE:'>q'})




