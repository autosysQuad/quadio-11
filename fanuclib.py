#!/usr/bin/python3

'''
DATE 						: 15/11/2020
ORGANISATION 				: AUTOSYS INDUSTRIAL SOLUTIONS PRIVATE LIMITED
ADDRESS 					: A148 / A252 ANTOP HILL WAREHOUSING COMPLEX, WADALA EAST, MUMBAI 400037
AUTHORS						: HARSHAD PATIL, AADITYA DAMANI
DESCRIPTION					: QUAD INDUSTRIAL IOT DATA ACQUISITION CODE 
VERSION						: V0.0.33
PYTHON VERSION				: PYTHON3
LICENSE 					: QUAD PLATFORM LICENSE REQUIRED
EMAIL						: INFO@AISPL.CO
WEBSITE						: WWW.AISPL.CO

REVISION HISTORY :
__________________________________________________

DATE OF REVISION			: 07/12/2021
VERSION CHANGE				: V0.0.5.13
AUTHORS 					: HARSHAD PATIL
DESCRIPTION OF CHANGE		: updated cyclehold/cycle stop (optional stop) as a step. 
'''
# import RPi.GPIO as GPIO
import time
import subprocess
import codecs
import math
from datetime import datetime, timedelta
from standardFunctions import standardFunctions
import json
import multiprocessing
from multiprocessing import Queue
import socket
from struct import pack,unpack
import struct
import threading
# import mongoDB
# from standardFunctions import sqliteDatabase
import sqliteDatabaseFunc as sqliteDb
import serial
import re
import os
import sys
import QuadEngine as quadEngine
import constants as constant
import logger as logger
global counter
import setproctitle
import heartBeat
import traceback
counter = 0
global startCycle
startCycle = [None]*6

class fanucFocas():
	FTYPE_OPN_REQU=0x0101;FTYPE_OPN_RESP=0x0102
	FTYPE_VAR_REQU=0x2101;FTYPE_VAR_RESP=0x2102
	FTYPE_CLS_REQU=0x0201;FTYPE_CLS_RESP=0x0202
	FRAME_SRC=b'\x00\x01'
	FRAME_DST=b'\x00\x02';FRAME_DST2=b'\x00\x01'
	FRAMEHEAD=b'\xa0\xa0\xa0\xa0'
	def __init__(self, ip="127.0.0.0", port=8193):
		self.configuration = standardFunctions()
		self.sock=None
		self.ip=ip
		self.port=port
		self.connected=False
		self.dataCollectionQueue = Queue()
		self.connectionfailure = 0

		self.minThreshold = 0
		self.maxThreshold = 0  #(10 Days)

		self.runStatusConditionsTable = [
								{"prevRun":"0" ,"currentRun":"1","Result":"STOP"},
								{"prevRun":"0" ,"currentRun":"2","Result":"HOLD"},
								{"prevRun":"0" ,"currentRun":"3","Result":"CYCLE-START"},

								{"prevRun":"1" ,"currentRun":"0","Result":"CT-STOP_CYCLE-RESET"},
								{"prevRun":"1" ,"currentRun":"2","Result":"CT-STOP_CT-HOLD"},
								{"prevRun":"1" ,"currentRun":"3","Result":"CT-STOP_CYCLE-CONTINUE"},

								{"prevRun":"2" ,"currentRun":"0","Result":"CT-HOLD_CYCLE-RESET"},
								{"prevRun":"2" ,"currentRun":"1","Result":"CT-HOLD_CT-STOP"},
								{"prevRun":"2" ,"currentRun":"3","Result":"CT-HOLD_CYCLE-CONTINUE"},

								{"prevRun":"3" ,"currentRun":"0","Result":"CYCLE-RESET"},
								{"prevRun":"3" ,"currentRun":"1","Result":"CT-STOP"},
								{"prevRun":"3" ,"currentRun":"2","Result":"CT-HOLD"}
							]

		units = {
					0:"mm",
					1:"inch",
					2:"degree",
					3:"mm/minute",
					4:"inch/minute",
					5:"rpm" ,
					6:"mm/round",
					7:"inch/round",
					8:"%",
					9:"Ampere",
					10:"Second"
				}

	def traceCondition(self,currentStat , prevStat):
		if int(currentStat) == int(prevStat):
			return None
		else:
			for conditions in self.runStatusConditionsTable:
				if int(conditions["currentRun"]) == int(currentStat) and  int(conditions["prevRun"]) == int(prevStat):
					return conditions["Result"]
		return "Condition Does not match ==>  currentStat: "+str(currentStat) + " & prevStat: " +str(prevStat)


	def connect(self):
		try:
			self.sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock.settimeout(5)
			try:
				self.sock.connect((self.ip,self.port))
				self.connectionfailure = 0
			except Exception as e:
				self.connectionfailure = self.connectionfailure + 1
				logger.errorLog("ERROR-FLFF-001: "+ str(e) + str(self.ip) + str(self.connectionfailure))
				if self.connectionfailure > 10 :
					logger.errorLog("process is about in restart in 30 Seconds...")
					time.sleep(30)
					sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"ip",str(self.ip))
					os.kill(int(os.getpid()), 9)
					# os.kill(int(os.getpid()), 9)
					
				return False
			
			self.sock.sendall(self.encap(fanucFocas.FTYPE_OPN_REQU,fanucFocas.FRAME_DST))
			data=self.decap(self.sock.recv(1500))
			if data["ftype"]==fanucFocas.FTYPE_OPN_RESP:
				self.connected=True
			if self.getsysinfo():
				self.axesctl=int(self.sysinfo['axes'])
				self.axesmax=int(self.sysinfo['maxaxis'])
				self.cnctype=self.sysinfo['cnctype'].decode()
				self.cncmttype=self.sysinfo['mttype'].decode()
			else:
				logger.errorLog("ERROR-FLFF-002.1: "+ str("sysinfo not received ,  trying to reconnect") )
				self.disconnect()
				self.connect()
			# GPIO.output(constant.heartBeatLed, True)
		except Exception as e:
			logger.errorLog("ERROR-FLFF-002: "+ str(e) )
			# GPIO.output(constant.heartBeatLed, False)
			# time.sleep(0.5)
			# GPIO.output(constant.heartBeatLed, True)
			# time.sleep(0.5)
			self.sock=None
			self.connected=False
			pass
		return self.connected

	def productionMonitoring(self ,datas , MACHINEID ):
		# while True:
		# 	try:
		# 		mData = self.dataCollectionQueue.get()
		# 		if "productionCounter" in mData:
		# 			for prodCounts in mData["productionCounter"]:
		# 				for confPoint in self.configDatas["productionCount"]:
		# 					if confPoint["name"] == prodCounts["name"]:
		# 						if confPoint["cycleEnd"] == "True":
		# 							print(confPoint["name"])
		# 							print(confPoint["stationNumber"])
		# 							print(prodCounts["value"])

		# 							print("cycle end")
		# 						else:
		# 							pass

		# 					else:
		# 						pass
		# 		else:
		# 			pass
		# 		# preRecData = recData
		# 		time.sleep(0.6)
		# 	except KeyboardInterrupt:
		# 			print()
		# 			subprocess.check_output("Taskkill /PID %d /F" % int(os.getpid()))


		# + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + + +
		
		alarmList = ["","EAlarm","Battery Low","FAN FAULT","PS Warning","FSSB Warning","Insulate warning","Encoder Warning","PMC Alarm"]
		stepsData = []
		stepStartTime = None
		startCycletime = None
		stationNo = 1
		eAlarmStartTime = None
		alarmStartTime = None
		alarm2StartTime = None
		alarmmsg = None
		partName = "aisplnoop"

		# dataToUpdate = {"CT_runningStatus":"0"}
		# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":MACHINEID})

		sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",0,"ip",self.ip)
		sqliteDb.updateDataWhereClause("aliveStatusTable","machineId",MACHINEID,"ip",self.ip)

		currentRunStatus = None
		firstRunFlag = True
		prevRunStatus = 0
		prevResultcondition = 0
		CT_run_bit = False
		prev_mData = 0
		toolNum = 1
		reworkFlag = False
		cycDisableFlag = False
		alarmOn = False
		sTime = 0
		cycleCompletionFlag = True
		cycleEnd = False
		productCounts = 0
		motionFlag = 0
		prevOffsetData = None
		partnameAtcyleStart = None
		masterPartname  = "aisplnoop"
		partNameDictonarry = {}
		ignoreSpindle = False

		if "spindleSpeed" in datas:
			if datas["spindleSpeed"] == "False" or datas["spindleSpeed"] == "false":
				ignoreSpindle = True
		
		actSped = 0

		while True:
			try:
				mData = self.dataCollectionQueue.get()
				# print(mData)
				if self.configuration.timeNow() - sTime > 0.9 :
					# self.configuration.timeNow()
					sTime = self.configuration.timeNow()
					packet = {
								"machineId": MACHINEID,
								"dataId": self.configuration.getDataId(),
								"date": mData["date"],
								"type":"analog"
							}
					if "spindlespeed" in mData:
						if mData["spindlespeed"] != None :
							dataPck = []
							for data_fet in mData["spindlespeed"]:
								dataPck.append({"name":"spindlespeed-"+str(data_fet[0]),"value":data_fet[1],"date":mData["date"]})
							# print(dataPck)
							packet.update({"spindleSpeeds":dataPck})
					
					if "spindleLoad" in mData:
						if mData["spindleLoad"] != None:
							dataPck = []
							for data_fet in mData["spindleLoad"]:
								dataPck.append({"name":"spindleLoad-"+str(data_fet[0]),"value":data_fet[1],"date":mData["date"]})
							# print(dataPck)
							packet.update({"spindleLoads":dataPck})

					if "servoLoad" in mData:
						if mData["servoLoad"] != None:
							dataPck = []
							for data_fet in mData["servoLoad"]:
								dataPck.append({"name":"servoLoad-"+str(data_fet[0]),"value":data_fet[1],"date":mData["date"]})
							# print(dataPck)
							packet.update({"servoLoads":dataPck})


					if "servo_current" in mData:
						if mData["servo_current"] != None:
							dataPck = []
							for data_fet in mData["servo_current"]:
								dataPck.append({"name":"servo_current-"+str(data_fet[0]),"value":data_fet[1],"date":mData["date"]})
							# print(dataPck)
							packet.update({"metadata":dataPck})

					if "f_value" in mData:
						if mData["f_value"] != None:
							packet.update({"feedRates":[{"name":"feed","value":mData["f_value"],"date":mData["date"]}]})
					
					if "set_feed_value" in mData:
						if mData["set_feed_value"] != None:
							if "metadata" in packet:
								packet["metadata"].append({"name":"setFeedrate","value":mData["set_feed_value"],"date":mData["date"]})
							else:
								packet.update({"metadata":[{"name":"setFeedrate","value":mData["set_feed_value"],"date":mData["date"]}]})
					
					quadEngine.physicalQueue.put(packet)
					packet = {}


				currentRunStatus = mData["statusInformation"]['run']
				# print("prevResultcondition at while start" , prevResultcondition)
				# print(mData["productionCounter"])
				if firstRunFlag:
					prev_mData = mData
					firstRunFlag = False
					prevResultcondition = self.traceCondition(currentRunStatus,prevRunStatus)
					prevRunStatus = currentRunStatus
					if int(currentRunStatus) == 3:
						# print("==> Cycle Start <==")
						startCycletime = stepStartTime = mData["date"]
				
						initPack = {
									  "machineId": MACHINEID,
									  "dataId": self.configuration.getDataId(),
									  "startDateTime": startCycletime,
									  "type": constant.cycleTimeStart_type
									}
						quadEngine.initialPulseQueue.put(initPack)
						CT_run_bit = True
						prev_mData["currentTool"] = 0
						reworkFlag = False
						# dataToUpdate = {"CT_runningStatus":"1"}
						# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":MACHINEID})
						sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",1,"ip",self.ip)


					# if int(mData["statusInformation"]['alarm']) > 1:
					# 	print( alarmList[int(mData["statusInformation"]['alarm'])]  + " START")

					runModeCondition = 1 
					if "runningMode" in self.configDatas:
						if "autoMode" in self.configDatas["runningMode"]:
							runModeCondition = int(self.configDatas["runningMode"]["autoMode"])

					if int(mData["statusInformation"]['aut']) == runModeCondition:
						runningMode = "AUTO"
					else:
						runningMode = "MANUAL"

					if str(mData["statusInformation"]['emegency']) == "1":
						# print("emergency pressed")
						eAlarmStartTime = mData["date"]
						alarmPacket = {
										  "machineId": MACHINEID,
										  "dataId": self.configuration.getDataId(),
										  "startDateTime": eAlarmStartTime,
										  "name": "EMERGENCY STOP",
										  "type": constant.emergency_type,
										  "statement": "emegency pressed"
										}
						quadEngine.initialPulseQueue.put(alarmPacket)
						logger.debugLog(alarmPacket)
					if int(mData["statusInformation"]['alarm']) > 1:
						alarmStartTime = mData["date"]
						alarmPacket = {
										  "machineId": MACHINEID,
										  "dataId": self.configuration.getDataId(),
										  "startDateTime": alarmStartTime,
										  "name": str(alarmList[int(mData["statusInformation"]['alarm'])]).replace('\x00',' '),
										  "type":  constant.alarm_type,
										  "statement": str(alarmList[int(mData["statusInformation"]['alarm'])]).replace('\x00',' ')  + " START"
										}
						quadEngine.initialPulseQueue.put(alarmPacket)
						logger.debugLog(alarmPacket)
			# except Exception as e:
			# 	logger.errorLog("ERROR-FLFF-072: " + str(e))
			# try:
				#print(mData["statusInformation"])
				#print(mData["offsets"])

				runModeCondition = 1 
				if "runningMode" in self.configDatas:
					if "autoMode" in self.configDatas["runningMode"]:
						runModeCondition = int(self.configDatas["runningMode"]["autoMode"])

				if int(mData["statusInformation"]['aut']) == runModeCondition:
					runningMode = "AUTO"
				else:
					runningMode = "MANUAL"

				if mData != prev_mData:
					if int(currentRunStatus) != int(prevRunStatus):
						resultcondition = self.traceCondition(currentRunStatus , prevRunStatus)
						# print(resultcondition , prevResultcondition   ,'   =--------------------result condition')
						logger.debugLog("cuurent result condition" + str(resultcondition) + ", prevRunStatus :"+str(prevRunStatus)+ " , currentRunStatus :" +str(currentRunStatus))
						if resultcondition != prevResultcondition:
							if resultcondition == "CYCLE-START" and (prevResultcondition == "CYCLE-RESET" or prevResultcondition == None) and CT_run_bit == False:
								# print("==> Cycle Start Normal<==")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								motionFlag = 1
								stepsData = []
								if mData["part_name"] != "aisplnoop" and mData["part_name"] != "" and mData["part_name"] != " ":
									partnameAtcyleStart = mData["part_name"]
								startCycletime = stepStartTime = mData["date"]
								initPack = {
											  "machineId": MACHINEID,
											  "dataId": self.configuration.getDataId(),
											  "startDateTime": startCycletime,
											  "type": constant.cycleTimeStart_type
											}
								quadEngine.initialPulseQueue.put(initPack)
								logger.debugLog(initPack,MACHINEID)
								CT_run_bit = True
								prev_mData["currentTool"] = 0
								reworkFlag = False
								cycDisableFlag = False
								# dataToUpdate = {"CT_runningStatus":"1"}
								# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":MACHINEID})
								sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",1,"ip",self.ip)

							elif resultcondition == "CYCLE-START" and prevResultcondition == "CT-STOP_CYCLE-RESET":
								# print("CT stop reset step end ; \nnew tool step start")
								# print("==> cycle start after stop reset <==")
								if stepStartTime == None:
									stepStartTime = mData["date"]

								if stepStartTime != None :
									step_switch = {"name": "CT-STOP-RESET", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"reset"}
								else:
									step_switch = {"name": "CT-STOP-RESET", "startDateTime":mData["date"],"endDateTime":mData["date"], "type":"reset"}

								# print(step_switch)
								stepsData.append(step_switch)
								stepStartTime = mData["date"]
								CT_run_bit = True
								cycDisableFlag = False
								prev_mData["currentTool"] = mData["currentTool"]
								# CT_run_bit = True
								#step - 
							elif resultcondition == "CYCLE-START" and prevResultcondition == "CT-HOLD_CYCLE-RESET":
								# print("CT hold reset step end ; \nnew tool step start")
								# print("==> cycle start after hold reset <==")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "CT-HOLD-RESET", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"reset"}
								# print(step_switch)
								stepsData.append(step_switch)
								stepStartTime = mData["date"]
								CT_run_bit = True
								cycDisableFlag = False
								prev_mData["currentTool"] = mData["currentTool"]
								# CT_run_bit = True
								# step -
							elif resultcondition == "CT-STOP" and prevResultcondition != None:
								# print("==> Cycle STOP <==")
								# print((prev_mData["currentTool"] ,"tool end in cycle stop"))
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "T" +str(prev_mData["currentTool"]), "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"Tools", "number": toolNum}
								# print(step_switch)
								stepsData.append(step_switch)
								toolNum += 1
								cycDisableFlag = True
								stepStartTime = mData["date"]
								prev_mData["currentTool"] = mData["currentTool"]
								# print("prevTool is force to currenttool----" , mData["currentTool"],prev_mData["currentTool"],"-------------------",mData["date"])
								# CT_run_bit = False
								#step -
							elif resultcondition == "CT-HOLD"  and prevResultcondition != None :
								# print("tool step end ; \nCT_HOLD step start")
								# print("==> Cycle HOLD <==")
								# print((prev_mData["currentTool"] ,"tool end in cycle hold"))
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "T" +str(prev_mData["currentTool"]), "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"Tools", "number": toolNum}
								# print(step_switch)
								stepsData.append(step_switch)
								# print(mData["currentTool"] ,  prev_mData["currentTool"] ,"\n" , step_switch)
								toolNum += 1
								cycDisableFlag = True
								stepStartTime = mData["date"]
								prev_mData["currentTool"] = mData["currentTool"]
								
							elif resultcondition == "CT-STOP_CYCLE-RESET" and prevResultcondition != None:
								# print("CT_STOP step end ; \nreset step start")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								# print("==> Cycle stop Reset <==")
								step_switch = {"name": "CT-STOP", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_stop"}
								# print(step_switch)
								stepsData.append(step_switch)
								stepStartTime = mData["date"]
								cycDisableFlag = False
								prev_mData["currentTool"] = mData["currentTool"]
								# CT_run_bit = False
								#step -
							elif resultcondition == "CT-STOP_CYCLE-RESET" and prevResultcondition == None:
								resultcondition = None
								prevResultcondition = None
							elif resultcondition == "CT-HOLD_CYCLE-RESET" and (prevResultcondition != None or prevResultcondition != "HOLD" or prevResultcondition != "STOP"):
								# print("==> Cycle HOLD Reset <==")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "CT-HOLD", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_hold"}
								# print(step_switch)
								stepsData.append(step_switch)
								stepStartTime = mData["date"]
								cycDisableFlag = False
								prev_mData["currentTool"] = mData["currentTool"]
								# CT_run_bit = False
							elif resultcondition == "CT-HOLD_CYCLE-RESET" and (prevResultcondition == None or prevResultcondition == "HOLD" or prevResultcondition == "STOP"):
								resultcondition = None
								prevResultcondition = None
								#step -
							elif resultcondition == "CT-STOP_CYCLE-CONTINUE":
								# print("==> Cycle Stop and continue <==")
								if stepStartTime == None:
									stepStartTime = mData["date"]

								step_switch = {"name": "CT-STOP_CYCLE-CONTINUE", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_stop_continue"}
								# print(step_switch)
								stepsData.append(step_switch)
								if toolNum > 1 :
									reworkFlag = False
								cycDisableFlag = False
								# print(mData["currentTool"],"  ",mData["date"], "cycle continue with tool after stop")
								stepStartTime = mData["date"]
								# CT_run_bit = True
								prev_mData["currentTool"] = mData["currentTool"]
								#step -
							elif resultcondition == "CT-HOLD_CYCLE-CONTINUE":
								# print("==> Cycle HOLD and continue<==")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "CT-HOLD_CYCLE-CONTINUE", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_hold_continue"}
								# print(step_switch)
								stepsData.append(step_switch)
								cycDisableFlag = False
								if toolNum > 1 :
									reworkFlag = False
								# print(mData["currentTool"] ,"  ",mData["date"], "cycle continue with tool after hold")
								stepStartTime = mData["date"]
		
								prev_mData["currentTool"] = mData["currentTool"]
								#step -
							elif resultcondition == "CYCLE-RESET":
								logger.debugLog("CYCLE-RESET" )
								# print("==> CYCLE-RESET ==> counterValue",productCounts , mData["MasterCounter"])
							
							elif resultcondition == "CT-STOP_CT-HOLD":
								# print("==> CT-STOP_CT-HOLD<==")
								if stepStartTime == None:
									stepStartTime = mData["date"]

								if toolNum > 1 :
									reworkFlag = False
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "CT-STOP", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_stop_hold"}
								stepsData.append(step_switch)
								stepStartTime = mData["date"]

							elif resultcondition == "CT-HOLD_CT-STOP":
								# print("==> CT-HOLD_CT-STOP <==")
								if stepStartTime == None:
									stepStartTime = mData["date"]
								if toolNum > 1 :
									reworkFlag = False
								step_switch = {"name": "CT-HOLD", "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"ct_hold_stop"}
								stepsData.append(step_switch)
								stepStartTime = mData["date"]

							prevResultcondition = resultcondition
						prevRunStatus = currentRunStatus

					if "spindlespeed" in mData:
						if mData["spindlespeed"] != None :
							spndspd = []
							for data_fet in mData["spindlespeed"]:
								spndspd.append(int(data_fet[1]))
							actSped = max(spndspd)

							if motionFlag == 0 and int(mData["statusInformation"]['motion']) == 1 and actSped > 100:
								motionFlag = 1
								startCycletime = stepStartTime = mData["date"]
								if stepStartTime == None:
											stepStartTime = mData["date"]
								initPack = {
											"machineId": MACHINEID,
											"dataId": self.configuration.getDataId(),
											"startDateTime": startCycletime,
											"type": constant.cycleTimeStart_type
											}
								quadEngine.initialPulseQueue.put(initPack)
								logger.debugLog(initPack,MACHINEID)
								CT_run_bit = True
								prev_mData["currentTool"] = 0
								reworkFlag = False
								cycDisableFlag = False
								# dataToUpdate = {"CT_runningStatus":"1"}
								# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":MACHINEID})
								sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",1,"ip",self.ip)

					if "productionCounter" in mData:
						# print("productionCounter is in mData" , mData["productionCounter"])
						if mData["productionCounter"] != prev_mData["productionCounter"]:
							for prodCounts , prevProdCounts in zip(mData["productionCounter"],prev_mData["productionCounter"]):
								for confPoint in self.configDatas["productionCount"]:
									if confPoint["name"] == prodCounts["name"]:
										if confPoint["cycleEnd"] == "True" and prodCounts["value"] != prevProdCounts["value"]:
											cycleCompletionFlag = False
											cycleEnd = True
											productCounts = prodCounts["value"]
											stationNo = confPoint["stationNumber"]
											# print("productCounts is :",productCounts)
										elif prodCounts["value"] != prevProdCounts["value"]:
											productCounts = prodCounts["value"]
											stationNo = confPoint["stationNumber"]
										
									else:
										pass
					else:
						productCounts = 0
						# print("======================= productCounts setting to zero" , mData)
						pass
					# print(mData["offsets"])
					# logger.debugLog(mData["offsets"])
					if "offsets" in mData:
						if mData["offsets"] != prev_mData["offsets"] :
							# jsonStr.update({"offsets":offsetData})
							logger.debugLog(str(mData["offsets"])+"--------------------------change of values" , MACHINEID)

					if mData["part_name"] != "aisplnoop" and mData["part_name"] != "" and mData["part_name"] != " ":
						partName = mData["part_name"]
					else:
						if prev_mData["part_name"] != "aisplnoop" and prev_mData["part_name"] != "" and prev_mData["part_name"] != " ":
							partName = prev_mData["part_name"]


					if mData["MasterCounter"] != prev_mData["MasterCounter"] and cycleCompletionFlag == True:
						cycleEnd = True
					if cycleEnd == True:
						CT_run_bit = False
						endCycletime = mData["date"]
						if stepStartTime == None:
							stepStartTime = mData["date"]
						# print("==> Cycle End <==" , reworkFlag , cycDisableFlag , mData["currentTool"] ,prev_mData["currentTool"])
						if reworkFlag == True and cycDisableFlag == False:	
							tool_switch = {"name": "T" +str(mData["currentTool"]), "startDateTime":stepStartTime,"endDateTime":endCycletime, "type":"Tools", "number": toolNum}
							stepsData.append(tool_switch)
						elif reworkFlag == False and cycDisableFlag == False :
							if stepStartTime != endCycletime:
								tool_switch = {"name": "T" +str(prev_mData["currentTool"]), "startDateTime":stepStartTime,"endDateTime":endCycletime, "type":"Tools", "number": toolNum}
								stepsData.append(tool_switch)
							else:
								pass

						if partnameAtcyleStart == None:
							partnameAtcyleStart = partName

						logger.debugLog("this is partdictionarry = "+ str(partNameDictonarry))
						if partNameDictonarry:
							max_value = max(partNameDictonarry.values())
							for key, value in partNameDictonarry.items():
								if value == max_value:
									masterPartname = key
						else:pass
						jsonStr = {
								"dataId":self.configuration.getDataId(),
								"machineId": MACHINEID,
								"type": constant.cycleTime_type,
								"startDateTime":startCycletime,
								"endDateTime":endCycletime,
								"actualCount":productCounts,
								"steps": stepsData,
								"stationNo":stationNo,
								"runningMode": runningMode,
								"totalCount" : mData["MasterCounter"],
								"metadata":[{
												"totalPowerOnTime":mData["totalPowerOnTime"],
												"date": mData["date"],
												"name": "Total Power ON Time",
												"unit": "seconds"
											},
											{
												"totalOperationalTime":mData["totalOperationalTime"],
												"date": mData["date"],
												"unit": "seconds",
												"name": "Total Operational Time"
											},
											{
												"totalCuttingTime":mData["totalCuttingTime"],
												"date": mData["date"],
												"unit": "seconds",
												"name": "Total Cutting Time"
											}],
								# "partId": partnameAtcyleStart
								"partId": masterPartname
							}
						# print(jsonStr)
						if "cycleTime" in datas:
							if datas["cycleTime"] == 0 or datas["cycleTime"] == "0":
								pass
							else:
								jsonStr.update({"actualCycleTime" : mData["time_minute"]*60 + (mData["time_millisec"]/1000)})
						else:
							jsonStr.update({"actualCycleTime" : mData["time_minute"]*60 + (mData["time_millisec"]/1000)})
						data = ""
						if "offsets" in mData:
							# print(mData["offsets"])
							if len(mData["offsets"]) > 0 :
								if "wearOffset" in mData["offsets"][0]:
									if mData["offsets"] != prevOffsetData :
										jsonStr.update({"offsets":mData["offsets"]})
										data = mData["offsets"]
										prevOffsetData = mData["offsets"]
						# print(offsetData)
						seconds = self.configuration.returnSec(jsonStr["startDateTime"], jsonStr["endDateTime"])
						if self.minThreshold < seconds and seconds < self.maxThreshold :
							try:
								actualCycleRunSequence = []
								for step in jsonStr["steps"]:
									try:
										if "number" in step:
											actualCycleRunSequence.append(step["name"].replace(".0",""))
									except Exception as e:
										pass

								if self.reworkEnable == 1:
									try:
										file1 = open(constant.runningProgram, 'r')
										Lines = file1.readlines()
										progToolRunArray = []
										m30LineNo = None
										reworkDetected = 0
										for count,line in enumerate(Lines):
											if line[0] == "T":
												if line[0:2] == "T0":
													x = line.replace("T0","T")
													x = x.replace("\n","")
													progToolRunArray.append({"toolName":x[0:4],"lineNo":count})
												else:
													progToolRunArray.append({"toolName":line[0:5],"lineNo":count})
											if line.find("M30") != -1:
												m30LineNo = count
												break
										if m30LineNo == None:
											m30LineNo = len(Lines)
										
										runSeq = []
										prevTool = 0
										for tool in actualCycleRunSequence:
											if prevTool != tool:
												runSeq.append(tool)
												prevTool = tool

										progRunSeq = []
										progPrevTool = 0
										rework_stage = 0
										for tool in progToolRunArray:
											if progPrevTool != tool["toolName"]:
												progRunSeq.append(tool["toolName"])
												progPrevTool = tool["toolName"]
										
										if runSeq == progRunSeq:
											reworkDetected = 0
											# jsonStr.update({"type":constant.cycleTime_type})
											# print("Correct Cycle on stage 1")
											pass
										else:
											if len(progRunSeq) >= len(runSeq):
												for count,value in enumerate(progRunSeq):
													try:
														if value == runSeq[count]:
															pass
														else:
															logger.logData(constant.reworkLogFile,str(runSeq) + "Actual cycle stesp tools")
															logger.logData(constant.reworkLogFile,str(progRunSeq) + "Tool list in program")
															logger.logData(constant.reworkLogFile,"INFO-FLFF-001 : Rework detected in tool sequence missmatch ")
															logger.debugLog("INFO-FLFF-001 : Rework detected in tool sequence missmatch ")
															# print("Rework detected in tool sequence missmatch")
															rework_stage = 1
															break
													except:
														missedTool_line = progToolRunArray[count]["lineNo"]
														for line in Lines[missedTool_line : m30LineNo+1]:
															if line[0] == ("G"):
																reworkDetected = 1
																break
															else:
																pass
														if reworkDetected == 1:
															logger.logData(constant.reworkLogFile,str(runSeq) + "Actual cycle stesp tools")
															logger.logData(constant.reworkLogFile,str(progRunSeq) + "Tool list in program")
															logger.logData(constant.reworkLogFile,"INFO-FLFF-002 : Rework detected stage 1")
															logger.logData(constant.reworkLogFile,"Rework detected stage 1")
															# print("Rework detected stage 1")
															rework_stage = 2
															break
														else:
															reworkDetected = 0
															# print("Correct Cycle")
											else:
												# print("insidle else")
												logger.logData(constant.reworkLogFile,str(runSeq) + "Actual cycle stesp tools")
												logger.logData(constant.reworkLogFile,str(progRunSeq) + "Tool list in program")
												logger.logData(constant.reworkLogFile,"INFO-FLFF-003 : Inside else, cycle run tools are more than actual machine program")
												logger.errorLog(str(runSeq) + "Actual cycle stesp tools")
												logger.errorLog(str(progRunSeq) + "Tool list in program")
												logger.errorLog("INFO-FLFF-003 : Inside else, cycle run tools are more than actual machine program")


										if rework_stage > 0 :
											reworkDetected = 0
											matchCount = 0
											toolArry = []
											# print(progRunSeq)
											for count ,toolRun in enumerate(progRunSeq): 
												try:
													# print(toolRun , count)
													if matchCount >=  len(runSeq) :
														# print(toolRun , "missing tool / Half cycle detecetd")
														logger.logData(constant.reworkLogFile,str(runSeq) + "Actual cycle stesp tools")
														logger.logData(constant.reworkLogFile,str(progRunSeq) + "Tool list in program")
														logger.logData(constant.reworkLogFile,"INFO-FLFF-004 : missing tool / Half cycle detecetd")
														logger.debugLog(str(runSeq) + "Actual cycle steps tools")
														logger.debugLog(str(progRunSeq) + "Tool list in program")
														logger.debugLog("INFO-FLFF-004 : missing tool / Half cycle detecetd , considered as complete cycle")
														logger.errorLog("INFO-FLFF-004 : missing tool / Half cycle detecetd , considered as complete cycle")
														reworkDetected = -1
														break
													else:
														try:
															if toolRun == runSeq[matchCount]:
																matchCount = matchCount +1
																# print("match")
																toolArry.append({"toolRun":toolRun , "progSeqNo":count , "progLineNo":progToolRunArray[count]["lineNo"]+1, "flag":"match"})
															else:
																# print("missed")
																toolArry.append({"toolRun":toolRun , "progSeqNo":count , "progLineNo":progToolRunArray[count]["lineNo"]+1 ,  "flag":"missed"})
														except Exception as e:
															logger.errorLog("INFO-FLFF-005 : missed" + toolRun + "in except not found : error==> "+str(e))
															# print(e)
															pass
												except Exception as e: 
													# print(e)
													logger.errorLog("ERROR-FLFF-0103 : "+str(e))
											missedToolQue = Queue()
											for number ,tool in enumerate(toolArry):
												if tool["flag"] == "missed":
													missedToolQue.put(tool)
												elif tool["flag"] == "match":
													if (missedToolQue.qsize() > 0):
														for Q_data in range(0,missedToolQue.qsize()):
															lastMissedTool = missedToolQue.get()
															if tool["progSeqNo"] > lastMissedTool["progSeqNo"]:
																# print(lastMissedTool ,tool)
																currentTool_line = tool["progLineNo"]
																missedTool_line = lastMissedTool["progLineNo"]						 
																for line in Lines[missedTool_line : currentTool_line]:
																	if line[0] == ("G"):
																		reworkDetected = 1
																		break
																	else:
																		pass
										
										if  self.reworkEnable == 1:
											if reworkDetected == 1:
												jsonStr.update({"type":constant.cycleRework_type})
												logger.errorLog("INFO-FLFF-005 : Rework detected stage 2")
												# logger.debugLog("ERROR-FLFF-0103 : "+str(e))
												# print("Rework detected stage 2")
											elif reworkDetected == 0:
												jsonStr.update({"type":constant.cycleTime_type})
												logger.errorLog("INFO-FLFF-006 : Correct Cycle stage 2")
												# print("Correct Cycle stage 2")
											elif reworkDetected == -1:
												jsonStr.update({"type":constant.cycleTime_type})

												logger.errorLog("INFO-FLFF-007 : "+ str(jsonStr))
												logger.errorLog("INFO-FLFF-007 : tool run missing/Half cycle/ considered as correct cycle")
												# print("tool run missing/Half cycle/ considered as correct cycle")
										else:
											jsonStr.update({"type":constant.cycleTime_type})

									except Exception as e:
										logger.errorLog(" ERROR-FLFF-0104 : rework detection error"+ str(e))
										pass

							except Exception as e:
								logger.errorLog(" ERROR-FLFF-0105 : rework detection error"+ str(e))
								pass
							if partNameDictonarry:
								quadEngine.cycletimeQueue.put(jsonStr)
							else:
								logger.debugLog("Rejcted CYcleTime besocs no PartName in Dictionarry ----------------------")
								quadEngine.rejectedCycletimeQueue.put(jsonStr)
							
							# print(jsonStr)
						else:
							quadEngine.rejectedCycletimeQueue.put(jsonStr)
						cycleEnd = False
						motionFlag = 0
						logger.debugLog({	"startDateTime":startCycletime,
											"endDateTime":endCycletime,
											"actualCount":productCounts,
											"totalCount" : mData["MasterCounter"],
											"partId": partnameAtcyleStart,
											"stationNo":stationNo,
											"offsets":data,
											"STEP_len":len(stepsData)
										} , MACHINEID)
						stepsData = []
						# dataToUpdate = {"CT_runningStatus":"0"}
						# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":MACHINEID})
						sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",0,"ip",self.ip)
						prev_mData["MasterCounter"] = mData["MasterCounter"]
						prevResultcondition = None
						partNameDictonarry = {}
						# print("prevResultcondition at counter increment" , prevResultcondition)
					
					if CT_run_bit == True and cycDisableFlag == False:
						
						if actSped > 100 or ignoreSpindle == True:
							if mData["part_name"] in partNameDictonarry:
								partNameDictonarry[mData["part_name"]] = partNameDictonarry[mData["part_name"]]+1
							else : partNameDictonarry.update({mData["part_name"]:1})

						if mData["currentTool"] != prev_mData["currentTool"]:
							# print("currentTool :",mData["currentTool"] , "prev Tool : ", prev_mData["currentTool"] , mData["date"])
							if int(prev_mData["currentTool"]) == 0:
								reworkFlag = True
								toolNum = 1
								stepStartTime = mData["date"]
								# print(mData["currentTool"] ,"first tool start")
								
							else:
								if mData["part_name"] != "aisplnoop" and mData["part_name"] != "" and mData["part_name"] != " ":
									partnameAtcyleStart = mData["part_name"]
								else: partnameAtcyleStart = partName
								
								if stepStartTime == None:
									stepStartTime = mData["date"]
								step_switch = {"name": "T" +str(prev_mData["currentTool"]), "startDateTime":stepStartTime,"endDateTime":mData["date"], "type":"Tools", "number": toolNum}
								stepsData.append(step_switch)
								# print((prev_mData["currentTool"] ,"tool end"))
								# print(step_switch)
								# print((mData["currentTool"] ,"tool start"))
								reworkFlag = False
								toolNum += 1
								stepStartTime = mData["date"]
							prev_mData["currentTool"] = mData["currentTool"]


					if mData["statusInformation"]['alarm'] != prev_mData["statusInformation"]['alarm']:
						if mData["statusInformation"]['alarm'] > 1:
							alarmStartTime = mData["date"]
							alarmPacket = {
											  "machineId": MACHINEID,
											  "dataId": self.configuration.getDataId(),
											  "startDateTime": alarmStartTime,
											  "name": str(alarmList[int(mData["statusInformation"]['alarm'])]).replace('\x00',' '),
											  "type":  constant.alarm_type,
											  "statement": str(alarmList[int(mData["statusInformation"]['alarm'])]).replace('\x00',' ') + " START"
											}
							quadEngine.initialPulseQueue.put(alarmPacket)
							logger.debugLog(alarmPacket)
						elif  mData["statusInformation"]['alarm'] == 0 and prev_mData["statusInformation"]['alarm'] > 0:
							if alarmStartTime != None:
								alarmPacket =	{
												  "machineId": MACHINEID,
												  "dataId": self.configuration.getDataId(),
												  "startDateTime": alarmStartTime,
												  "endDateTime": mData["date"],
												  "name": str(alarmList[int(prev_mData["statusInformation"]['alarm'])]).replace('\x00',' '),
												  "type": constant.alarm_type,
												  "statement":  str(alarmList[int(prev_mData["statusInformation"]['alarm'])]).replace('\x00',' ') + " released"
												}
								quadEngine.alarmsQueue.put(alarmPacket)
								logger.debugLog(alarmPacket , MACHINEID)
								alarmStartTime =None

					if mData["statusInformation"]['emegency'] != prev_mData["statusInformation"]['emegency'] and str(mData["statusInformation"]['emegency']) == "1":
						# print("emergency pressed")
						eAlarmStartTime = mData["date"]
						alarmPacket = {
										  "machineId": MACHINEID,
										  "dataId": self.configuration.getDataId(),
										  "startDateTime": eAlarmStartTime,
										  "name": "EMERGENCY STOP",
										  "type": constant.emergency_type,
										  "statement": "emegency pressed"
										}
						logger.debugLog(alarmPacket)
						quadEngine.initialPulseQueue.put(alarmPacket)
					elif mData["statusInformation"]['emegency'] != prev_mData["statusInformation"]['emegency'] and str(mData["statusInformation"]['emegency']) == "0":
						# print("emergency released")
						if eAlarmStartTime !=  None:
							alarmPacket =	{
											  "machineId": MACHINEID,
											  "dataId": self.configuration.getDataId(),
											  "startDateTime": eAlarmStartTime,
											  "endDateTime": mData["date"],
											  "name": "EMERGENCY STOP",
											  "type": constant.emergency_type,
											  "statement": "emergency released"
											}
							quadEngine.alarmsQueue.put(alarmPacket)
							logger.debugLog(alarmPacket , MACHINEID)
							eAlarmStartTime = None

					if mData["alarmcode"] > 0:
						if mData["alarmcode"] != prev_mData["alarmcode"]:
							alarmOn = True
							alarm2StartTime = mData["date"]
							alarmmsg = self.readsysalarmmsg(mData["alarmcode"]).replace('\\x00',' ')
							alarmmsg = self.readsysalarmmsg(mData["alarmcode"]).replace('\\x01',' ')
							alarmmsg = self.readsysalarmmsg(mData["alarmcode"]).replace('\\x03',' ')
							alarmmsg = self.readsysalarmmsg(mData["alarmcode"]).replace('\\n',' ')
							alarmmsg = self.readsysalarmmsg(mData["alarmcode"]).replace('\\x0',' ')
							alarmPacket = {	
												"dataId":self.configuration.getDataId(),
												"machineId":MACHINEID,
												"startDateTime" :alarm2StartTime,
												"type": constant.alarm_type,
												"name": alarmmsg,
												"statement":" Alarm Generated"
											}
							logger.debugLog(alarmPacket)
							quadEngine.initialPulseQueue.put(alarmPacket)

						else:
							if alarmOn == True:
								if alarm2StartTime != None:
									alarmPacket = {
													"dataId":self.configuration.getDataId(),
													"machineId":MACHINEID,
													"startDateTime" :alarm2StartTime,
													"endDateTime": mData["date"],
													"type": constant.alarm_type,
													"name": alarmmsg,
													"statement":" Alarm Released"
												}
									logger.debugLog(alarmPacket,MACHINEID)
									quadEngine.alarmsQueue.put(alarmPacket)
								alarmOn = False
								alarm2StartTime = None
	
				prev_mData = mData
			except Exception as e:
				# raise e
				logger.errorLog(str(e)+"  productionMonitoring")
			
			time.sleep(0.01)

	def allDataCollection(self, datas ,machineId):
		# dataToUpdate = {"processId":str(os.getpid()),"exceptionErrorCode":"0" , "machineId":machineId}
		# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":machineId})
		sqliteDb.updateDataWhereClause("aliveStatusTable","processId",os.getpid(),"ip",self.ip)
		if "productionCount" in  datas:
			datas['noOfStations'] = len(datas["productionCount"])
			pass
		else:
			datas['noOfStations'] = 1
			datas["productionCount"]= [0]
			datas["productionCount"][0]={} 
			datas["productionCount"][0]["address"]="6711"
			datas["productionCount"][0]["dataType"]="param"
			datas["productionCount"][0]["offset"]="0"
			datas["productionCount"][0]["idleValue"]="0"
			datas["productionCount"][0]["cycleEnd"]="False"
			datas["productionCount"][0]["name"]="actualCounter"
			datas["productionCount"][0]["stationNumber"]="1"

		self.configDatas = datas
		dataCounters = [0]*int(self.configDatas["noOfStations"])
		dataDict = {}
		keyArray = ["statusInformation",
					"MasterCounter",
					"productionCounter",
					"time_millisec",
					"time_minute",
					"currentTool",
					"part_name",
					"f_value",
					"spindlespeed",
					"spindleLoad",
					"servoLoad",
					"date",
					"offsets",
					"alarmcode",
					"totalPowerOnTime",
					"totalOperationalTime",
					"totalCuttingTime",
					"servo_current",
					"set_feed_value"
					]
		dTime = 0
		logger.debugLog("Data collection initialised : "+self.ip)
		state = True
		part_name = tempPartName = "aisplnoop"
		prevProgNum = 0
		prevRunStatus = None

		runningProgram = constant.runningProgram
		try:
			prevProgram = open(runningProgram,"r")
		except:
			prevProgram = None
			pass
		offsetDArr = []
		plist = None

		retry = True
		responseData = None
		# while retry:
		# 	try:
		# 		plist = self.listprog()
		# 		timeoutCount = 0
		# 		retry = False
		# 	except Exception as e:
		# 		self.disconnect()
		# 		time.sleep(1)
		# 		self.connect()
		# 		retry = True
		# 		timeoutCount = timeoutCount + 1
		# 		if timeoutCount > 30 :
		# 			logger.errorLog("ERROR-FLFF-0103.3: "+ str("Error when plist"))

		while True:
			if self.configuration.timeNow() - dTime >0.4:
				try:
					state = not state
					# print(self.configuration.getDateTime(), "at start")

					dTime = self.configuration.timeNow()
					progNum = self.readprognum()
					plist = self.listprog()
					try:
						tempPartName = re.sub('[()]', '', plist[progNum["run"]]['comment'])
						if len(tempPartName) > 3:
							part_name = tempPartName ##current running part
					except:
						part_name = "aisplnoop"
					statusInformation = self.statinfo()
					MasterCounter = self.readparam(0,6712)[6712]['data'][0]   	#mater counter
					try:
						for count, dataPoint in enumerate(self.configDatas["productionCount"]):
							if dataPoint["dataType"] == "macro":
								# dataCounters[count] = self.readmacro(int(dataPoint["address"]))[int(dataPoint["address"])]
								dataCounters[count] = {"name":dataPoint["name"],"value":self.readmacro(int(dataPoint["address"]))[int(dataPoint["address"])]}
							elif dataPoint["dataType"] == "param":
								# dataCounters[count] = self.readparam(0,int(dataPoint["address"]))[int(dataPoint["address"])]['data'][0]
								dataCounters[count] = {"name":dataPoint["name"],"value":self.readparam(0,int(dataPoint["address"]))[int(dataPoint["address"])]['data'][0]}

					except :
						pass 
					# productionCounter = self.readparam(0,6711)[6711]['data'][0]		#running counter
					# time.sleep(0.1)
					time_millisec = self.readparam(0,6757)[6757]['data'][0]	#running cycle time in milliseconds
					time_minute = self.readparam(0,6758)[6758]['data'][0]		#running cycletime time elapsed in Minute
					currentTool = self.readmacro(4120)[4120]								#current tool selected
					# plist = self.listprog()

					if self.reworkEnable == 1 or self.offsetEnble == 1:		
						try:
							if prevProgNum != progNum['run']:
								try:
									curprogram = str(self.getprog(str(progNum['run'])))
									if curprogram != str(-1) :
										if curprogram != prevProgram:
											f = open(runningProgram, "w")
											f.write(curprogram)
											f.close()
										prevProgNum = progNum['run']
								except Exception as e:
									logger.errorLog("ERROR-FLFF-0102.3: "+ str("Error when program:"+str(progNum['run'])+"  "+ str(e) ) )

							try:
								file = open(runningProgram,"r")
								dataDump = file.readlines()
								pass
							except Exception as e:
								logger.errorLog("ERROR-FLFF-0102.4: "+ str("Error when program:"+str(progNum['run'])+"  runningProgram: "+runningProgram + "  "+str(e) ) )
								dataDump = []
							toolsArray = []
							tName = None
							offsets = {}
							for lines in dataDump:
								x = lines.find("(")
								if lines[0] == "T" and x != -1:
									# print(lines)
									try:
										q = 1
										for datas in toolsArray:
											# print(datas,datas.strip("\n") , "datas" , lines[0:x-1] , "lines[0:x-1]")
											if datas[0:x-1] == lines[0:x-1]:
												# print("break")
												q = 0
												break
											else:
												q = 1
										if q == 1:
											toolsArray.index(lines[0:x-1])
									except:
										toolsArray.append(lines.strip(" ").strip("\n"))
								# else:
								# 	offsets = {}
								# 	toolsArray = []
							# print(toolsArray , "toolsArray")
							if  prevRunStatus != int(statusInformation['run']) and int(statusInformation['run']) == 3:
								offsetDArr= []
								if len(toolsArray) > 0:
									for tools in toolsArray:
										# print(tools)
										pos_1 = tools.find("(")
										pos_2 = tools.find(")")
										x = 1
										if pos_1 != -1 and pos_2 != -1 :
											comment = (tools[pos_1+1:pos_2])
											# print(comment , "comment")
											pos_3 = comment.find("+")
											if pos_3 != -1:
												comment_opName = comment[:pos_3]
												comment_wearName = comment[pos_3+1:]
												# print({"toolOperationName":comment_opName,"insertName":comment_wearName})
												offsets.update({"type":comment_opName[-1:],"toolOperationName":comment_opName[:-2],"insertName":comment_wearName})
											else :
												# offsets.update({"toolOperationName":comment})
												x = 0
											# offsetAddress = tools
											if x == 1 and str(self.offsetEnble) == str(1):
												offsetAddress = (tools[:pos_1].strip(" ")[-2:])
												# print(offsetAddress , "offsetAddress")
												tName =tools.replace("T0" ,"T")[:pos_1-1]
												try:	
													offsets.update({"wearOffset":{
																	"x":self.readmacro(10000+int(offsetAddress))[10000+int(offsetAddress)],
																	"y":self.readmacro(14000+int(offsetAddress))[14000+int(offsetAddress)],
																	"z":self.readmacro(11000+int(offsetAddress))[11000+int(offsetAddress)],
																	"dCode":self.readmacro(12000+int(offsetAddress))[12000+int(offsetAddress)]
															}})
													offsets.update({"geometricOffset":{
																	"x": self.readmacro(15000+int(offsetAddress))[15000+int(offsetAddress)],
																	"y": self.readmacro(16000+int(offsetAddress))[16000+int(offsetAddress)],
																	"z": self.readmacro(19000+int(offsetAddress))[19000+int(offsetAddress)],
																	"dCode":self.readmacro(13000+int(offsetAddress))[13000+int(offsetAddress)]
															}})
												except Exception as e:
													logger.errorLog("ERROR-FLFF-0102: "+ str("Error when reading wear offsets:"+str(e)) )										
												offsets.update({"name":tName.strip('\n').strip(" ")})
												offsetDArr.append(offsets)
												offsets = {}
											else:
												offsets = {}
									# print(offsetDArr,"offsetDArr\n")	

							prevRunStatus = int(statusInformation['run'])
						except Exception as e:
							logger.errorLog("ERROR-FLFF-0102.1: "+ str(":"+str(e)) )
							part_name = tempPartName ##current running part


					# except:
					# 	part_name = "aisplnoop"
					f_value=self.readactfeed()										# actaul feedrae
					spindlespeed=self.readspindlespeed()										#actual spm (Set RPM)
					spindleLoad=self.readspindleload()								#actual spindle load
					servoLoad =self.readservoload()									#actual servo load
					servo_current =self.readservoCurrent()
					# set_spindlespeed=self.readspindlespeed()							#actual spindle speed'
					set_feed_value = self.readsetfeed()
					myTime = self.configuration.getDateTime()
					alarmcode = self.readsysalarm()
					totalPowerOnTime = int(self.readparam(0,6750)[6750]['data'][0])*60
					totalOperationalTime_sec = int(self.readparam(0,6751)[6751]['data'][0])
					totalOperationalTime_min = int(self.readparam(0,6752)[6752]['data'][0])
					totalOperationalTime = totalOperationalTime_min*60+totalOperationalTime_sec
					totalCuttingTime_sec = int(self.readparam(0,6753)[6753]['data'][0])
					totalCuttingTime_min = int(self.readparam(0,6754)[6754]['data'][0])
					totalCuttingTime = totalCuttingTime_min*60+totalCuttingTime_sec
					dataArray = [	
									statusInformation,
									MasterCounter,
									dataCounters,
									time_millisec,
									time_minute,
									currentTool,
									part_name,
									f_value,
									spindlespeed,
									spindleLoad,
									servoLoad,
									myTime,
									offsetDArr,
									alarmcode,
									totalPowerOnTime,
									totalOperationalTime,
									totalCuttingTime,
									servo_current,
									set_feed_value
								]
				
					for i in range(0 , len(dataArray)):
						dataDict.update({keyArray[i]:dataArray[i]})
						
					self.dataCollectionQueue.put(dataDict)
					# offsetDArr= []
					dataDict = {}
				except Exception as e:
					logger.errorLog("ERROR-FLFF-007: "+ str(e) )
					# print("ERROR-FLFF-007: "+ str(e) )
					count = 0
					dataDict = {}
					while (not self.connect()):
						self.connect()
						count = count + 1
						logger.errorLog("ERROR-FLFF-0092: "+ str("Retrying connection... try:"+str(count)) )
						# dataToUpdate = {"processId":"0","exceptionErrorCode":"103" , "machineId":machineId}
						# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":machineId})

						logger.errorLog("ERROR-FLFF-0101.1: "+ str("Killing the process allDataCollection :"+machineId))
						if count > int(constant.machineReconnectionAttemps) :
							logger.errorLog("ERROR-FLFF-0101: "+ str("System rebooting after "+str(constant.machineReconnectionAttemps)+" attempts to connect..."))
							# sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"ip",self.ip)
							count = 0
							try:
								# dataToUpdate = {"processId":"0","exceptionErrorCode":"102" , "machineId":machineId}
								# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":machineId})
								sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"ip",self.ip)
								logger.errorLog("ERROR-FLFF-0101.1: "+ str("Killing the process allDataCollection :"+machineId))
								os.kill(int(os.getpid()), 9)
								# subprocess.check_output("Taskkill /PID %d /F" % int(os.getpid()))
							except Exception as e:
								print(e)
								pass
				except KeyboardInterrupt:
					sys.exit()	
			# 	time.sleep(0.1)
			time.sleep(0.01)

	def machineDataCollection(self,machineIP,PORT,machineId,data,minThreshold,maxThreshold):
		procAlreadyRunFlag = 1
		self.minThreshold = minThreshold
		self.maxThreshold = maxThreshold
		self.ip= str(machineIP)
		self.port=int(PORT)
		try:
			self.offsetEnble = int(data["offsets"])
		except Exception as e:
			self.offsetEnble = 0
			pass
		try:
			self.reworkEnable = int(data["rework"])
		except Exception as e:
			self.reworkEnable = 0
			pass

		x = (os.popen("ps aux|grep quad-machineDataCollection").read())
		sentence = ' '.join(filter(None,x.split(' ')))
		processes = sentence.split("\n")
		for process in processes:
			p = process.split(" ")
			# print(p , "process")
			lenP = len(p)
			if lenP > 1: 
				procName = (p[lenP-1])
				if procName == "quad-machineDataCollection:-"+machineId :
					logger.errorLog("ERROR-FLFF-066: "+ str("quad-machineDataCollection:-"+machineId + ": >> Process Already Running") )
					procAlreadyRunFlag = 0

		if procAlreadyRunFlag == 1:			
			count = 0
			setproctitle.setproctitle("quad-machineDataCollection:-"+machineId)
			logger.errorLog("FOCAS connection Initialised with " + str(self.ip) +":"+str(self.port))
			# sqliteDb.updateDataWhereClause("aliveStatusTable","processId",os.getpid(),"ip",self.ip)
			# dataToUpdate = {"processId":str(os.getpid()),"exceptionErrorCode":"0" , "machineId":machineId}
			# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":machineId})
			sqliteDb.updateDataWhereClause("aliveStatusTable","processId",os.getpid(),"ip",self.ip)
			# print(os.getpid() , "PID updated")
			while (not self.connect()):
				self.connect()
				logger.errorLog("ERROR-FLFF-009: "+ str("Retrying connection ...") )
				count = count + 1
				if count > int(constant.machineReconnectionAttemps) :
					# logger.errorLog("ERROR-FLFF-010: "+ str("System rebooting after "+str(constant.machineReconnectionAttemps)+" attempts to connect..."))
					count = 0
					try:
						# dataToUpdate = {"processId":"0","exceptionErrorCode":"101" , "machineId":machineId}
						# mongoDB.updateData("liveStatus",dataToUpdate,{"machineId":machineId})
						sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"ip",self.ip)
						logger.errorLog("ERROR-FLFF-010.1: "+ str("Killing the process machineDataCollection :"+machineId))
						# subprocess.check_output("Taskkill /PID %d /F" % int(os.getpid()))
						os.kill(int(os.getpid()), 9)
					except Exception as e:
						print(e)
						pass

			try:
				# print("STarting data collection")
				sqliteDb.updateDataWhereClause("aliveStatusTable","processId",os.getpid(),"ip",self.ip)
				x = threading.Thread(target=self.allDataCollection, args=(data,machineId,))
				y = threading.Thread(target=self.productionMonitoring ,args=(data,machineId,))
				# x = multiprocessing.Process(target=self.allDataCollection, args=(data,))
				# y = multiprocessing.Process(target=self.productionMonitoring ,args=(machineId,))
				# z = threading.Thread(target=self.frequencyFunction, args=(data["processData"],data["processData"]["frequency"],))
				x.start()
				y.start()
				# z.start()
				x.join()
				y.join()
				
			except Exception as e:
				logger.errorLog("ERROR-FLFF-008: "+ str(e) )
				pass

	def disconnect(self):
		if self.connected:
			try:
				self.sock.sendall(self.encap(fanucFocas.FTYPE_CLS_REQU,b''))
				data=self.decap(self.sock.recv(1500))
				if data["ftype"]==fanucFocas.FTYPE_CLS_RESP:
					return True
					
			except Exception as e:
				logger.errorLog("ERROR-FLFF-011: "+ str(e))
				pass
		return False


	def _req_rdsingle(self,c1,c2,c3,v1=0,v2=0,v3=0,v4=0,v5=0,pl=b""):
		"intern function - pack simple command"
		try:
			return self._req_rdmulti([self._req_rdsub(c1,c2,c3,v1,v2,v3,v4,v5,pl)])
		except Exception as e:
			logger.errorLog("ERROR-FLFF-012: "+ str(e))
			pass

	def _req_rdmulti(self,lst):
		"intern function - pack multiple commands - multipacket version"
		try:
			self.sock.sendall(self.encap(fanucFocas.FTYPE_VAR_REQU,lst))
			dat=b''
			while True: #MULTI-Packet
				dat+=self.sock.recv(1500)
				t=self.decap(dat)
				if not "missing" in t:
					break
			if t['len']<=0: #ZEROLENGTH/ERROR
				return {'len':-1,'error':-1,'suberror':0}
			if t['ftype']!=fanucFocas.FTYPE_VAR_RESP: #NOT RESPONSE
				return {'len':-1,'error':-1,'suberror':1}
			if len(lst) != len(t['data']): #WRONG subpacket-count
				return {'len':-1,'error':-1,'suberror':3}
			for x in range(len(t['data'])):
				cmd=lst[x][0:6]
				if t['data'][x].startswith(cmd):
					v=dict(zip(['error','errdetail','len'],unpack('>hhxxH',t['data'][x][6:14])))
					v['cmd']=unpack('>HHH',t['data'][x][:6]),
					v['data']=t['data'][x][14:]
					if len(lst)==1:
						return v
					t['data'][x]=v
				else:
					return {"len":-1,'error':-1,'suberror':2}
			return t
		except Exception as e:
			logger.errorLog("ERROR-FLFF-013: "+ str(e))
			pass
	

	def encap(self,ftype,payload,fvers=1):
		"intern function - Encapsulate packetdata"
		try:
			if ftype==fanucFocas.FTYPE_VAR_REQU:
				pre=[]
				if isinstance(payload,list):
					for t in payload:
						pre.append(pack(">H",len(t)+2)+t)
					payload=pack(">H",len(pre))+b''.join(pre)
				else:
					payload=pack(">HH",1,len(payload)+2)+payload
			return fanucFocas.FRAMEHEAD+pack(">HHH",fvers,ftype,len(payload))+payload
		except Exception as e:
			logger.errorLog("ERROR-FLFF-014: "+ str(e))
			pass

	def decap(self,data):
		"intern function - Decapsulate packetdata"
		try:
			if len(data)<10:
				return {"len":-1}
			if not data.startswith(b'\xa0'*4):
				return {"len":-1}
			fvers,ftype,len1=unpack(">HHH",data[4:10])
			if len1+10 != len(data):
				if (len1+10)>len(data):
					return {"len":-1,"missing":len1+10-len(data)}
				else:
					return {"len":-1}
			if len1==0:
				return {"len":0,"ftype":ftype,"fvers":fvers,"data":b'0'}
			data=data[10:]
			if ftype==fanucFocas.FTYPE_VAR_RESP:
				re=[]
				qu=unpack(">H",data[0:2])[0]
				n=2
				for t in range(qu):
					le=unpack(">H",data[n:n+2])[0]
					re.append(data[n+2:n+le])
					n+=le
				return {"len":len1,"ftype":ftype,"fvers":fvers,"data":re}
			else: # ftype==FTYPE_OPN_RESP or ftype==FTYPE_CLS_RESP
				return {"len":len1,"ftype":ftype,"fvers":fvers,"data":data}
		except Exception as e:
			logger.errorLog("ERROR-FLFF-015: "+ str(e))
			pass
	

	def readparaminfo(self,num,count=1,param=1): #param=0 for settings
		try:
			if param==1:
				st=self._req_rdsingle(1,1,0x10,num,count)
			else:
				st=self._req_rdsingle(1,1,0x2B,num,count)
			if st["len"]<0:
				return
			r={"next":unpack(">i",st["data"][4:8])[0],"before":unpack(">i",st["data"][0:4])[0]}
			for pos in range(8,st["len"],8):
				r[unpack(">i",st["data"][pos:pos+4])[0]]={'type':unpack(">i",st["data"][pos+4:pos+8])[0]}
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-016: "+ str(e))
			pass

	def readparaminfo2(self,num,count=1):
		try:
			st=self._req_rdsingle(1,1,0xa0,num,count,0,0,0x10000)
			if st["len"]<0:
				return
			r={"next":unpack(">i",st["data"][4:8])[0],"before":unpack(">i",st["data"][0:4])[0]}
			for pos in range(8,st["len"],4*5):
				r[unpack(">i",st["data"][pos:pos+4])[0]]=dict(zip(['size','array','unit','dim','input','display','others'],unpack(">hhhhhhh",st["data"][pos+4:pos+4+2*7])))
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-017: "+ str(e))
			pass


	def getMachineDate(self):
		try:
			st=self._req_rdsingle(1,1,0x45,0)
			if st["len"]==0xc:
				return unpack(">HHH",st["data"][0:6])
		except Exception as e:
			logger.errorLog("ERROR-FLFF-018: "+ str(e))
			pass

	def getMachineTime(self):
		try:
			st=self._req_rdsingle(1,1,0x45,1)
			if st["len"]!=0xc:
				return
			return unpack(">HHH",st["data"][-6:])
		except Exception as e:
			logger.errorLog("ERROR-FLFF-019: "+ str(e))
			pass
		
	def getMachineDateTime(self): 
		try:
			st=self._req_rdmulti([self._req_rdsub(1,1,0x45,0),self._req_rdsub(1,1,0x45,1)])
			if st["len"]<0:
				return
			if len(st["data"]) != 2:
				return
			if st['data'][0]['error']!=0 or st["data"][1]['error']!=0:
				return
			if st['data'][0]['len'] == 0xc and st['data'][0]['len'] == 0xc:
				return datetime.datetime(*unpack(">HHHHHH",st["data"][0]['data'][0:6]+st["data"][1]['data'][-6:])).timetuple()
		except Exception as e:
			logger.errorLog("ERROR-FLFF-020: "+ str(e))
			pass

	def _req_rdsub(self,c1,c2,c3,v1=0,v2=0,v3=0,v4=0,v5=0,pl=b""):
		return pack(">HHHiiiii",c1,c2,c3,v1,v2,v3,v4,v5)+pl


	ABS,REL,REF,SKIP,DIST,ABSWO,RELWO=[2 ** x for x in range(7)]
	ALLAXIS=-1
	
	def readaxes(self,what=1,axis=ALLAXIS): #v
		try:
			r=[]
			axvalues=(("ABS",fanucFocas.ABS,4),("REL",fanucFocas.REL,6),
						("REF",fanucFocas.REF,1),("SKIP",fanucFocas.SKIP,8),
						("DIST",fanucFocas.DIST,7),("ABSWO",fanucFocas.ABSWO,0),
						("REFWO",fanucFocas.RELWO,2))
			for u,v,w in axvalues:
				if what & v:
					r.append(self._req_rdsub(1,1,0x26,w,axis))
			st=self._req_rdmulti(r)
			if st["len"]<0:
				return
			r={}
			for x in st["data"]:
				ret1=[]
				if x['len'] < 0:
					ret1=None
				else:
					for pos in range(0,x['len'],8):
						if pos>8*self.axesctl:
							continue
						value=x['data'][pos:pos+8]
						ret1.append(self._decode8(value))
				for u,v,w in axvalues:
					if what & v:
						r[u]=ret1
						what &= ~v
						break
			return 
		except Exception as e:
			logger.errorLog("ERROR-FLFF-021: "+ str(e))
			pass
	
	def _decode8(self,val):
		"intern function - decode value from 8 bytes"
		try:
			if val[5]==2 or val[5]==10:
				if val[-2:]==b'\xff'*2:
					return float('Nan')
				else:
					# print(val[0:4], "   val 0 to 4")
					# print(unpack(">i",val[0:4]), "   unpack")
					return unpack(">i",val[0:4])[0]/val[5]**val[7]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-022: "+ str(e))
			pass
	


	def getsysinfo(self):
		try:
			st=self._req_rdsingle(1,1,0x18)
			if st["len"]==0x12:
				self.sysinfo=dict(zip(['addinfo','maxaxis','cnctype','mttype','series','version','axes'],
				unpack(">HH2s2s4s4s2s",st["data"])))
				return 1
		except Exception as e:
			logger.errorLog("ERROR-FLFF-023: "+ str(e))
			return 0
			pass


	FORMAT_AXIS,FORMAT_TOOLOFF,FORMAT_MACRO,FORMAT_WORKZOFF,FORMAT_CUTFR=0,1,2,3,4;
	def getformat(self,type=0): #v
		"get typespecific numberformat"
		try:
			st=self._req_rdsingle(1,1,0x1b,type)
			if st["len"]>=4+2*2:
				n={'type':type,'count':unpack(">i",st["data"][0:4])[0]}
				t=[]
				for x in range(4,st["len"],4):
					t.append(dict(zip(['decinput','decoutput'],unpack(">HH",st["data"][x:x+4]))))
				if len(t)>1:
					n["dec"]=t
				else:
					n.update(t[0])
				return n
		except Exception as e:
			logger.errorLog("ERROR-FLFF-024: "+ str(e))
			pass
	
	def readparam(self,axis,first,last=None,param=1): #param=0 for settings
		"""
		Read Parameter(s)
		or Setting(s) - Paramter with setting-attribut
		"""
		# print(conn.cnctype)
		try:
			# if self.cnctype=='31' or self.cnctype==' 0' or self.cnctype=='32':
			firstrequest = self.readparam2(axis,first,last,param)
			if firstrequest:
				return firstrequest
			if last is None:last=first
			if param==1:
				st=self._req_rdsingle(1,1,0x0e,first,last,axis)
			else:
				st=self._req_rdsingle(1,1,0x29,first,last,axis)
			if st["len"]<0:
				return
			r={}
			for pos in range(0,st["len"],self.sysinfo["maxaxis"]*4+8):
				varname,axiscount,valtype=unpack(">IhH",st["data"][pos:pos+8])
				values={"type":valtype,"axis":axiscount,"data":[]}
				for n in range(pos+8,pos+self.sysinfo["maxaxis"]*4+8,4):
					value=st["data"][n:n+4]
					if valtype==0:
						value=[(value[-1] >> n)& 1 for n in range(7,-1,-1)] #bit 1bit
					elif valtype==1:
						value=value[-1] #byte
					elif valtype==2:
						value=unpack(">h",value[-2])[0] #short
					elif valtype==3:
						value=unpack(">i",value)[0] #int
					if axiscount != -1:
						values["data"].append(value)
						break
					else:
						values["data"].append(value)
				r[varname]=values
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-025: "+ str(e))
			pass


	def readparam2(self,axis,first,last=None,param=1): #param=0 for settings
		"""
		Read Parameter(s)info
		or Setting(s)info - Paramter with setting-attribut
		"""
		try:
			if last is None:last=first
			if param==1:
				st=self._req_rdsingle(1,1,0x8d,first,last,axis)
			else:
				st=self._req_rdsingle(1,1,0x90,first,last,axis)
			if st["len"]<0:
				return
			r={}
			for pos in range(0,st["len"],self.sysinfo["maxaxis"]*8+8):
				varname,axiscount,valtype=unpack(">IhH",st["data"][pos:pos+8])
				values={"type":valtype,"axis":axiscount,"data":[]}
				for n in range(pos+8,pos+self.sysinfo["maxaxis"]*8+8,8):
					value=st["data"][n:n+8]
					if valtype==0:
						value=[(value[3] >> n)& 1 for n in range(7,-1,-1)]
					elif valtype==1 or valtype==2 or valtype==3:
						value=unpack(">i",value[0:4])[0]
					elif valtype==4:
						value=self._decode8(value)  #real
					if axiscount != -1:
						values["data"].append(value)
						break
					else:
						values["data"].append(value)
				r[varname]=values
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-026: "+ str(e))
			pass

	def readparameters(self,axis,first,last): #Elegant Version
		try:
			paracmd=0x0e if self.cnctype!=b'31' else 0x8d
			paralen=4 if self.cnctype!='31' else 8

			st=self._req_rdmulti([self._req_rdsub(1,1,0x10,first,1),
				self._req_rdsub(1,1,0x10,last,1),
				self._req_rdsub(1,1,paracmd,first,last,axis)])
			if st["len"]<0:
				return
			f=dict(zip(['before','next','num'],unpack(">iii",st["data"][0]['data'][:12])))
			l=dict(zip(['before','next','num'],unpack(">iii",st["data"][1]['data'][:12])))
			if f['num'] != first:
				first=f['num']
			if l['num'] != last:
				last=l['before']
			error,length,data=st["data"][2]['error'],st["data"][2]['len'],st["data"][2]['data']
			r={}
			while True:
				for pos in range(0,length,self.sysinfo["maxaxis"]*paralen+8):
					varname,axiscount,valtype=unpack(">IhH",data[pos:pos+8])
					values={"type":valtype,"axis":axiscount,"data":[]}
					for n in range(pos+8,pos+self.sysinfo["maxaxis"]*paralen+8,paralen):
						value=data[n:n+paralen]
						if valtype==0:
							value=[(value[3] >> n)& 1 for n in range(7,-1,-1)] #bit 1bit
						elif valtype==4:
							value=self._decode8(value)  #real
						elif valtype==1 or valtype==2 or valtype==3: #byte,shert,long
							value=unpack(">i",value[0:4])[0]
						if axiscount != -1:
							values["data"]=value
							break
						else:
							values["data"].append(value)
					r[varname]=values
					first=varname+1
				if error==2:
					st=self._req_rdsingle(1,1,paracmd,first,last,axis)
					error=st['error']
					if st["len"]<0:
						break
					data=st['data']
					length=st['len']
				else:
					break
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-027: "+ str(e))
			pass


	
	def readdiag(self,axis,first,last=None):
		try:
			if last is None:last=first
			st=self._req_rdsingle(1,1,0x30,first,last,axis)
			if st["len"]<0:
				return
			r={}
			for pos in range(0,st["len"],self.sysinfo["maxaxis"]*4+8):
				varname,axiscount,valtype=unpack(">IhH",st["data"][pos:pos+8])
				values={"type":valtype,"axis":axiscount,"data":[]}
				for n in range(pos+8,pos+self.sysinfo["maxaxis"]*4+8,4):
					value=st["data"][n:n+4]
					if valtype==4 or valtype==0:
						value=value[-1] #bit 1bit / Byte
					elif valtype==1:
						value=unpack(">h",value[-2])[0] #short
					elif valtype==2:
						value=unpack(">i",value)[0] #int
					elif valtype==3:
						value=[(value[-1] >> n)& 1 for n in range(7,-1,-1)] #bit 8bit
					if axiscount != -1:
						values["data"].append(value)
						break
					else:
						values["data"].append(value)
				r[varname]=values
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-028: "+ str(e))
			pass

	def readdrives(self):
		"""
		Get drive-names
		returns names
		"""
		try:
			st=self._req_rdsingle(1,1,0xae)
			if st["len"]<0:
				return
			ret=[]
			for t in range(0,st["len"],12):
				a=st["data"][t:t+12]
				ret.append(a[0:a.find(b'\0')].decode())
			return ret
		except Exception as e:
			logger.errorLog("ERROR-FLFF-029: "+ str(e))
			pass

	def readdir_current(self,fgbg=1): #31i
		"""
		Get current directory
		requests 1 (default) for foreground or 2 for background
		returns directoryname
		"""
		try:
			st=self._req_rdsingle(1,1,0xb0,fgbg)
			if st["len"]<0:
				return
			p=st["data"].split(b'\0', 1)[0]
			return p.decode()
		except Exception as e:
			logger.errorLog("ERROR-FLFF-030: "+ str(e))
			pass

	def readdir_info(self,dir): #31i
		try:
			buffer=bytearray(0x100)
			bdir=dir.encode()
			buffer[0:len(bdir)]=bdir
			st=self._req_rdsingle(1,1,0xb4,0,0,0,0,256,buffer)
			if st["len"]>=8:
				return dict(zip(['dirs','files'],unpack(">ii",st["data"])))
			return None
		except Exception as e:
			logger.errorLog("ERROR-FLFF-031: "+ str(e))
			pass
			return None


	def readdir(self,dir,first=0,count=10,type=0,size=1): #30i
		try:
			buffer=bytearray(0x100)
			bdir=dir.encode()
			buffer[0:len(bdir)]=bdir
			st=self._req_rdsingle(1,1,0xb3,first,count,type,size,256,buffer)
			# print(st)
			x=[]
			if st["len"]>=8:
				for t in range(0,st["len"],128):
					n=dict(zip(['type','datetime','unkn','size','attr','name','comment','proctimestamp'],unpack(">h12s6sII36s52s12s",st["data"][t:t+128])))
					# print(n.decode())
					del n['unkn']
					if n['type']==1:
						n['comment']=n['comment'].split(b'\0', 1)[0].decode()
						n['datetime']=None
					else:
						n['comment']=n['comment'].split(b'\0', 1)[0].decode()
						n['size']=None
						n['datetime']=None
					n['name']=n['name'].split(b'\0', 1)[0].decode()
					n['type']='D' if n['type']==0 else 'F'
					x.append(n)
				return(x)
			return None
		except Exception as e:
			logger.errorLog("ERROR-FLFF-032: "+ str(e))
			pass
			return None

	def readdir_complete(self,dir): #30i
		try:
			t=self.readdir_info(dir)
			n=t['dirs']+t['files']
			ret=[]
			for t in range(0,n,10):
				x=self.readdir(dir,first=t,count=10)
				if not x is None:
					ret.extend(x)
				else:
					break
			return ret
		except Exception as e:
			logger.errorLog("ERROR-FLFF-033: "+ str(e))
			pass



	# def readactspindlespeed(self):
	# 	"""
	# 	Get actual spindlespeed
	# 	returns spindlespeed
	# 	"""
	# 	try:
	# 		st=self._req_rdsingle(1,1,0x25)
	# 		return self._decode8(st['data']) if st['len']==8 else None
	# 	except Exception as e:
	# 		logger.errorLog("ERROR-FLFF-034: "+ str(e))
	# 		pass
	

	def readmacro(self,first,last=None):
		try:
			if last is None: last=first
			st=self._req_rdsingle(1,1,0x15,first,last)
			if st["len"]<=0:
				return
			r={}
			for pos in range(0,st["len"],8):
				r[first]=self._decode8(st["data"][pos:pos+8])
				first+=1
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-035: "+ str(e))
			pass

	def readmacro2(self,first,count=1):
		try:
			st=self._req_rdsingle(1,1,0xa7,first,count)
			if st["len"]<=0:
				return
			r={}
			for pos in range(0,st["len"],8):
				r[first]=unpack(">d",st["data"][pos:pos+8])[0]
				first+=1
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-036: "+ str(e))
			pass
	
	PMC2CNC,CNC2PMC,PMC2MCH,MCH2PMC,MSG,INTRLY,TIMER,KEEPRLY,CNT,DATA=list(range(10))
	TBYTE,TWORD,TLONG=list(range(3))
	def readpmc(self,datatype,section,first,count=1):# n=conn.readpmc(1,9,2204,1)
		try:
			last=first+(1<<datatype)*count-1
			st=self._req_rdsingle(2,1,0x8001,first,last,section,datatype)
			if st["len"]<=0:
				return
			r={}
			for x in range(st["len"]>>datatype):
				pos=(1<<datatype)*x
				if datatype==0:
					value=st["data"][pos]
				elif datatype==1:
					value=unpack(">H",st["data"][pos:pos+2])[0]
				elif datatype==2:
					value=unpack(">I",st["data"][pos:pos+4])[0]
				r[first+(1<<datatype)*x]=value
			return r
		except Exception as e:
			logger.errorLog("ERROR-FLFF-037: "+ str(e))
			pass
	
	def readexecprog(self,chars=256):
		try:
			st=self._req_rdsingle(1,1,0x20,chars)
			if st["len"]<=4:
				return
			return {"block":unpack(">i",st["data"][0:4])[0],"text":st["data"][4:].decode()}
		except Exception as e:
			logger.errorLog("ERROR-FLFF-038: "+ str(e))
			pass
	
	def readprognum(self):
		try:
			st=self._req_rdsingle(1,1,0x1c)
			if st["len"]<8:
				return
			return {"run":unpack(">i",st["data"][0:4])[0],"main":unpack(">i",st["data"][4:])[0]}
		except Exception as e:
			logger.errorLog("ERROR-FLFF-039: "+ str(e))
			return "aisplnoop"
			pass

	def readprogname(self): #31i
		"""
		Get current mainprogname
		returns name with path
		"""
		try:
			st=self._req_rdsingle(1,1,0xb9)
			if st["len"]<=0:
				return
			p=st["data"].split(b'\0', 1)[0]
			return p.decode()
		except Exception as e:
			logger.errorLog("ERROR-FLFF-040: "+ str(e))
			pass
	
	def settime(self,h=-1,m=0,s=0):
		try:
			if h is None:
				t=time.localtime()
				h,m,s=t.tm_hour,t.tm_min,t.tm_sec

			return self._req_rdsingle(1,1,0x46,1,0,0,0,12,pack(">xxxxxxHHH",h,m,s))['error']
		except Exception as e:
			logger.errorLog("ERROR-FLFF-041: "+ str(e))
			pass

	def _encode8(self,val,exp=2):
		"intern function - encode value to 8 bytes"
		try:
			if isinstance(val,int):
				return pack(">i",val)+b"\0\x02\0\0"
			else:
				return pack(">i",val[0:4])[0]/val[5]**val[7]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-042: "+ str(e))
			pass
	
	def listprog(self,start=1):
		ret={}
		try:
			while True:
				st=self._req_rdsingle(1,1,0x06,start,0x13,2)
				if st["len"] < -1:
					return None
				elif st["len"]==0:
					return ret
				for t in range(0,st["len"],72):
					number,size,comment=unpack(">II64s",st["data"][t:t+72])
					comment=comment.split(b'\0', 1)[0]
					start=number+1
					ret[number]={"size":size,"comment":comment.decode()}
		except Exception as e:
			logger.errorLog("ERROR-FLFF-043: "+ str(e))
			pass
	
	def getprog(self,name): #TEST Stream
		try:
			q=b''
			if isinstance(name,int):
				q=("O%04i-O%04i" % (name,name)).encode()
			elif isinstance(name,str):
				name=name.upper()
				if self.cnctype=='31':
					name="N:"+name
				else:
					if not name.startswith("O"):
						name="O"+name
					if name.find("-")==-1:
						name=name+"-"+name
				q=name.encode()
			else:
				return -1
			buffer=bytearray(0x204)
			self.sock2=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock2.settimeout(1)
			self.sock2.connect((self.ip,self.port))
			
			self.sock2.sendall(self.encap(fanucFocas.FTYPE_OPN_REQU,fanucFocas.FRAME_DST2))
			data=self.decap(self.sock2.recv(1500))
			buffer[0:4]=b'\x00\x00\x00\x01'
			buffer[4:4+len(q)]=q #buffer[4:15]=b'\x4f\x30\x31\x30\x30\x2d\x4f\x30\x31\x30\x30'
			self.sock2.sendall(self.encap(0x1501,buffer))
			data=self.decap(self.sock2.recv(1500))
			f=b''
			n=b''
			while True:
				n+=self.sock2.recv(1500)
				while len(n)>=10:
					if n[:4]==fanucFocas.FRAMEHEAD:
						fvers,ftype,flen=unpack(">HHH",n[4:10])
						if len(n)<flen:
							break
						n=n[10:]
						if ftype==0x1604: #a0 a0 a0 a0 00 02 16 04 05 00
							f+=n[:flen]
							n=n[flen:]
						elif ftype==0x1701: #a0 a0 a0 a0 00 02 17 01 00 00
							self.sock2.sendall(self.encap(0x1702,b'')) #a0 a0 a0 a0 00 01 17 02 00 00
							return f.decode()
					else:
						logger.errorLog("ERROR-FLFF-044.1:program not found ")
						pass
						return -1
			logger.errorLog("ERROR-FLFF-044.2: "+ str(e))
			pass
			return -1
		except Exception as e:
			logger.errorLog("ERROR-FLFF-044: "+"arguments pass" + str(name) +str(e) )
			pass
			return -1
		
	def readactfeed(self):
		try:
			st=self._req_rdsingle(1,1,0x24)
			return self._decode8(st['data']) if st['len']==8 else None
		except Exception as e:
			logger.errorLog("ERROR-FLFF-045: "+ str(e))
			pass
			return None
	
	

	def readsysalarm(self):
		try:
			st=self._req_rdsingle(1,1,0x1a)
			if st['len']==4:
				return struct.unpack(">i",st['data'][0:4])[0]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-064: "+ str(e))
			pass
			return None

	def readsysalarmmsg(self, alarmno):
		try:
			if alarmno > 0:
				baseTwo = int(math.log(alarmno,2))
				st=self._req_rdsingle(1,1,0x23,baseTwo,4,2,0x40)
				add = ""
				for x in range (int(st['len']/80)):
					start = (80*x) +16
					end  = (80*x) +42
					result = codecs.decode(st['data'][start:end])
					add = add +result
				return add
			else : return "no alarm"
		except Exception as e:
			logger.errorLog("ERROR-FLFF-065: "+ str(e))
			pass
			return None

	def readalarm(self):
		"Read alarm Bitfield"
		try:
			st=self._req_rdsingle(1,1,0x1a)
			if st["len"]!=4:
				return
			return unpack(">L",st["data"])[0]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-046: "+ str(e))
			pass

	def readalarmcode(self,type,withtext=0,maxmsgs=None,textlength=32):
		"Read alarm code / msg"
		#readalarmmsg	Returns Alarmcode+Msgtext	1,1,0x23,int32 Type,int32 MaxMsgs,int32 0 w/o or 1/2 with text,int32 MaxTextLength
		#											int32 AlarmCode,int32 AlarmType,int32 Axis,int32 TextLength,text/trash
		try:
			if maxmsgs is None:
				maxmsgs=int(self.sysinfo['axes'])
			st=self._req_rdsingle(1,1,0x23,type,maxmsgs,withtext,textlength)
			ret=[]
			if st["len"] < 0 :
				return
			for pos in range(0,st["len"],4*4+textlength):
				entry=dict(zip(['alarmcode','alarmtype','axis'],unpack(">iii",st["data"][pos:pos+4*3])))
				txlen=unpack(">i",st["data"][pos+4*3:pos+4*4])[0]
				if txlen>0 and withtext>0:
					entry["text"]=st["data"][pos+4*4:pos+4*4+txlen].decode()
				ret.append(entry)
			return ret
		except Exception as e:
			logger.errorLog("ERROR-FLFF-047: "+ str(e))
			pass

	def statinfo(self):
		# {'run': 3, 'edit': 0, 'alarm': 0, 'emegency': 0, 'motion': 0, 'aut': 1, 'mstb': 1}   response
		"""
		Get state of machine
		"""
		try:
			st=self._req_rdsingle(1,1,0x19,0)
			if self.cnctype in (' 0','16','31','32','21','30') and st["len"]==0xe:
				return dict(zip(['aut','run','motion','mstb','emegency','alarm','edit'],
				unpack(">HHHHHHH",st["data"])))
		except Exception as e:
			logger.errorLog("ERROR-FLFF-048: "+ str(e))
			pass
	
	def readaxesnames(self): #v
		try:
			st=self._req_rdsingle(1,1,0x89)
			if st["len"]<0:
				return
			ret=[]
			for t in range(0,st["len"],4):
				if t>4*self.axesctl:
					continue
				a=st["data"][t:t+4]
				ret.append(a[0:a.find(b'\0')].decode())
			return ret
		except Exception as e:
			logger.errorLog("ERROR-FLFF-049: "+ str(e))
			pass

	def readservoload(self):  # Percentage
		try:
			axisName=self.readaxesnames()
			st=self._req_rdsingle(1,1,0x56,1)
			if st["len"]<0:
				return
			ret=[]
			for t in range(0,st["len"],8):
				if t>8*self.axesctl-1:
					continue
				a=st["data"][t:t+4]
				ret.append(self.signed32bit(a))
			retData = []
			for count , axis in enumerate(axisName):
				retData.append((axis,ret[count]))
			return retData
		except Exception as e:
			pass
#CHG3
	def readsetfeed(self):
		try:
			feedRate_mm_per_revolution=self.readmacro(4109)[4109]
			if self.cncmttype.strip() == "T":
				setspindleSpeed = self.readmacro(4119)[4119]
				data = feedRate_mm_per_revolution * setspindleSpeed
				return data
			else:
				return feedRate_mm_per_revolution
				# print(len(self.cncmttype) , "need to strip")
		except Exception as e:
			logger.debugLog("ERROR-FLFF-045.1: "+ str(e))
			pass
			return None
		
		traceback.fo

	def readservoCurrent(self):  # Ampere
		try:
			axisName=self.readaxesnames()
			st=self._req_rdsingle(1,1,0x56,3)
			if st["len"]<0:
				return
			ret=[]
			for t in range(0,st["len"],8):
				if t>8*self.axesctl-1:
					continue
				a=st["data"][t:t+4]
				ret.append(self.signed32bit(a))
			retData = []
			for count , axis in enumerate(axisName):
				retData.append((axis,int(ret[count])/100))
			return retData
		except Exception as e:
			pass

	def signed32bit(self,hexval):
		bits = 16
		val = int(hexval.hex(), bits)
		if int(val) > 2147483647:
			r = 4294967296 - int(val)
			val = r*(1)
		return val

	def readsetting(self,axis,first,last=0):
		try:
			return self.readparam(axis,first,last=None,param=0)
		except Exception as e:
			logger.errorLog("ERROR-FLFF-051: "+ str(e))
			pass
	def readsettinginfo(self,num,count=1):
		try:
			return self.readparaminfo(num,count,param=0)
		except Exception as e:
			logger.errorLog("ERROR-FLFF-052: "+ str(e))
			pass

#----------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------
	# CHG1
	
	# def readactspm(self):
	# 	try:
	# 		st=self._req_rdsingle(1,1,0x25)
	# 		if st['len']==8:
	# 			return self._decode8(st['data'])
	# 	except Exception as e:
	# 		logger.errorLog("ERROR-FLFF-053: "+ str(e))
	# 		pass

	def readspindlespeed(self):  #RPM
		try:
			st=self._req_rdsingle(1,1,0xa4,1)
			noOfSpindles = self.signed32bit(st['data'])
			st=self._req_rdsingle(1,1,0x8a,-1)
			spindleNames=[]
			for t in range(0,st["len"],4):
				if t>4*noOfSpindles:
					continue
				a=st["data"][t:t+4]
				spindleNames.append(a[0:a.find(b'\0')].decode())
			st=self._req_rdsingle(1,1,0x40,7 , -1)
			ret = []
			for t in range(0,st["len"],8):
				if t>8*noOfSpindles:
					continue
				a=st["data"][t:t+4]
				ret.append(self.signed32bit(a))
			retData = []
			for count , spndleName in enumerate(spindleNames):
				retData.append((spndleName,int(ret[count])))

			return retData
		except Exception as e:
			pass
			print(e)

	def readalarm2(self):
		"Read alarm Bitfield"
		try:
			st=self._req_rdsingle(1,1,0x1a)
			if st["len"]!=4:
				return
			return unpack(">L",st["data"])[0]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-054: "+ str(e))
			pass
#-------------------------------------------++++++++++++++++++++++++---------------------------------------------------------------------------

	def cycleOn(self):
		try:
			st = self._req_rdsingle(1,1,0x19)
			return st['data'][3]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-055: "+ str(e))
			pass

	def readoperatormsg1(self):
		try:
			st=self._req_rdsingle(1,1,0x34,1)
			return codecs.decode(st['data'][8:])
		except Exception as e:
			logger.errorLog("ERROR-FLFF-056: "+ str(e))
			pass
	
	def readoperatormsg2(self):
		try:
			st=self._req_rdsingle(1,1,0x34,4)
			return codecs.decode(st['data'][8:])
		except Exception as e:
			logger.errorLog("ERROR-FLFF-057: "+ str(e))		
			pass
	
	# CHG2
	# def readspindleload(self):
	# 	try:
	# 		st=self._req_rdsingle(1,1,0x40,4,-1)
	# 		return self._decode8(st['data'])
	# 	except Exception as e:
	# 		logger.errorLog("ERROR-FLFF-058: "+ str(e))
	# 		pass

	def readspindleload(self):   #Percentage
		try:
			st=self._req_rdsingle(1,1,0xa4,1)
			noOfSpindles = self.signed32bit(st['data'])
			st=self._req_rdsingle(1,1,0x8a,-1)
			spindleNames=[]
			for t in range(0,st["len"],4):
				if t>4*noOfSpindles:
					continue
				a=st["data"][t:t+4]
				spindleNames.append(a[0:a.find(b'\0')].decode())
			st=self._req_rdsingle(1,1,0x40,4,-1)
			ret = []
			for t in range(0,st["len"],8):
				if t>8*noOfSpindles:
					continue
				a=st["data"][t:t+4]
				ret.append(self.signed32bit(a))
			retData = []
			for count , spndleName in enumerate(spindleNames):
				retData.append((spndleName,int(ret[count])))

			return retData
		except Exception as e:
			pass
			print(e)
	
	# def readspindlespeed(self):
	# 	try:
	# 		st=self._req_rdsingle(1,1,0x40,5,-1)
	# 		return self._decode8(st['data'])
	# 	except Exception as e:
	# 		logger.errorLog("ERROR-FLFF-059: "+ str(e))
	# 		pass
	
	# def readsetfeed(self):
	# 	try:
	# 		data=self.readmacro(4109)[4109]
	# 		return data
	# 	except Exception as e:
	# 		logger.debugLog("ERROR-FLFF-045.1: "+ str(e))
	# 		pass
	# 		return None

	# def readspindlespeed(self):  #RPM
	# 	try:
	# 		st=self._req_rdsingle(1,1,0xa4,1)
	# 		noOfSpindles = self.signed32bit(st['data'])
	# 		st=self._req_rdsingle(1,1,0x8a,-1)
	# 		spindleNames=[]
	# 		for t in range(0,st["len"],4):
	# 			if t>4*noOfSpindles:
	# 				continue
	# 			a=st["data"][t:t+4]
	# 			spindleNames.append(a[0:a.find(b'\0')].decode())
	# 		st=self._req_rdsingle(1,1,0x40,7 , -1)
	# 		ret = []
	# 		for t in range(0,st["len"],8):
	# 			if t>8*noOfSpindles:
	# 				continue
	# 			a=st["data"][t:t+4]
	# 			ret.append(self.signed32bit(a))
	# 		retData = []
	# 		for count , spndleName in enumerate(spindleNames):
	# 			retData.append((spndleName,int(ret[count])))

	# 		return retData
	# 	except Exception as e:
	# 		pass
	# 		print(e)
	
	def readaxisname(self):
		try:
			st=self._req_rdsingle(1,1,0x89)
		except Exception as e:
			logger.errorLog("ERROR-FLFF-060: "+ str(e))
			pass

	def readspindlenames(self): #v
		try:
			st=self._req_rdsingle(1,1,0x8a)
			if st["len"]<0:
				return
			ret=[]
			for t in range(0,st["len"],4):
				a=st["data"][t:t+4]
				ret.append(a[0:a.find(b'\0')].decode())
			return ret
		except Exception as e:
			logger.errorLog("ERROR-FLFF-061: "+ str(e))
			pass

	def readmyalarm(self):
		try:
			st=self._req_rdsingle(1,1,0x1a)
		#		return st
		#		print(st)
		#		st['data'] = b'\x00\x00\x00\x10'
			if st['len']==4:
		#			return codecs.decode(st['data'])
		#			return st['data'][0:3]
		#			return self._decode8(st['data'])
				return struct.unpack(">i",st['data'][0:4])[0]
		except Exception as e:
			logger.errorLog("ERROR-FLFF-062: "+ str(e))
			pass

	def readmyalarmmsg(self, alarmno):
		try:
			if alarmno > 0:

				baseTwo = int(math.log(alarmno,2))
				st=self._req_rdsingle(1,1,0x23,baseTwo,1,2,0x40)

				add = ""
				for x in range (int(st['len']/80)):
					start = (80*x) +16
					end  = (80*x) +42
					forres = codecs.decode(st['data'][start:end])
					add = add +forres
				return add
			else : return "no alarm"
		except Exception as e:
			logger.errorLog("ERROR-FLFF-063: "+ str(e))
			pass

class fanuc_RS232():
	def __init__(self ):
		# print(quadConfiguration)
		self.configuration = standardFunctions()
		self.serialPort= None
		self.connected=False
		self.ser = None
		self.dataCollectionQueue = Queue()
		self.retry = 0
		self.minThreshold = 0
		self.maxThreshold = 0
		# sqliteDb = sqliteDb
		self.heartBeatQueue = Queue()
		# .put(jsonStr)
		# .get()

	def connect(self,port,baudrate,parity=serial.PARITY_EVEN,stopbits=serial.STOPBITS_ONE,bytesize=serial.SEVENBITS,xonxoff = 1):
		
		if parity == "E":
			parity = serial.PARITY_EVEN
		elif parity == "O":
			parity = serial.PARITY_ODD
		elif parity == "N":
			parity = serial.PARITY_NONE

		if stopbits == 1 or stopbits == "1":
			stopbits = serial.STOPBITS_ONE
		elif stopbits == 2 or stopbits == "2":
			stopbits = serial.STOPBITS_TWO
		elif stopbits == 0 or stopbits == "0":
			stopbits = serial.STOPBITS_ZERO

		if bytesize == 7 or bytesize == "7":
			bytesize=serial.SEVENBITS
		elif bytesize == 8 or bytesize == "8":
			bytesize=serial.EIGHTBITS
		elif bytesize == 6 or bytesize == "6":
			bytesize=serial.SIXBITS

		try:
			self.ser = serial.Serial(
				# port='COM101',
				port=port,
				baudrate=baudrate,
				parity=parity,
				stopbits=stopbits,
				bytesize=bytesize,
				xonxoff = 1,
			)
			self.ser.isOpen()
		except Exception as e:
			errorOcurred = True
			# if self.retry > 20:
				# os.kill(int(os.getpid()), 9)
				# logger.errorLog("ERROR-FLFF-069: "+ str("rebooting in 30 Sec") )
				# time.sleep(30)
				# os.system("sudo reboot")
				# sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"machineId",configurations["machineId"])

			# sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"machineId",configurations["machineId"])
			if port == "/dev/ttyUSB0":
				try:
					self.ser = serial.Serial(
						# port='COM101',
						port="/dev/ttyUSB1",
						baudrate=baudrate,
						parity=parity,
						stopbits=stopbits,
						bytesize=bytesize,
						xonxoff = 1,
					)
					self.ser.isOpen()
					errorOcurred = False
				except Exception as e:
					pass
			if errorOcurred:
				x = (os.popen("dmesg|grep usb").read())
				logger.errorLog("USB STATS LOG: \r\n\n"+ str(x))
				logger.errorLog("ERROR- FLR2-001: "+ str(e))
				logger.errorLog("ERROR- FLR2-001: "+ str("Process will be restart in 10 Sec"))
				time.sleep(10)
				os.system("sudo pkill -f quad")
			# os.kill(int(os.getpid()), 9)
			# self.disconnect()
			# self.connect(self,port,baudrate,parity,stopbits,bytesize,xonxoff)
			# self.retry = self.retry + 1

	def disconnect(self):
		self.ser.close()

	
	def allDataCollection(self,configurations):
		datacollectionThread = multiprocessing.Process(target=self.machineDataCollection , args = (configurations,))
		# heartBeatThread = threading.Thread(target=self.machineDataCollection , args = (configurations,))
		datacollectionThread.start()
		
		heartBeatThread = threading.Thread(target=self.heratBeatCallFunction , args = (configurations,))
		heartBeatThread.start()

	def heratBeatCallFunction(self, arg):
		prevtime = time.time()
		machineStatus = None
		while True:
			try:
				machineStatus = self.heartBeatQueue.get(timeout=0.1)
			except Exception as err:
				pass
			if time.time() - prevtime > 120:
				if machineStatus == None:
					machineStatus = {"machineStatus":0}
				details = [[0,0,0,0,0,0,0,machineStatus["machineStatus"]]]
				heartBeat.heartBeatFuction(details, [arg["machineId"]])
				prevtime = time.time()
				time.sleep(2)

	def machineDataCollection(self,configurations):

		print ("-------------- starting mchinedatacolleciton  ---------------------------")
		try:
			if "minThreshold" in configurations: 
				self.minThreshold = configurations["minThreshold"]
				self.maxThreshold = configurations["maxThreshold"]
			else:
				self.minThreshold = 0
				self.maxThreshold  = 172800	
		except:
			self.minThreshold = 0
			self.maxThreshold  = 172800
			
		setproctitle.setproctitle("quad-datacollection:-" + configurations["machineId"])
		cycleStartTime = None
		# print(configurations)
		cycleEndTime = None
		try:
			self.connect(	port =configurations["serialPort"],
							baudrate = configurations["baudrate"],
							parity=configurations["parity"],
							stopbits=configurations["stopbits"],
							bytesize=configurations["bytesize"],
							xonxoff = configurations["xonxoff"],
						)
			logger.debugLog("Serial USB Connected")
		except Exception as e:
			logger.debugLog(str(e))
			raise e
		rawData = {}
		tool_raw_list = []
		current_tool = 0
		tool_sTime = 0
		prev_tool = 0
		flag_cycleComplete = 0
		flag_cycleStart = 0
		flag_tooling = 0
		toolNo = 1
		data = ''
		try:
			sqliteDb.updateDataWhereClause("aliveStatusTable","processId",os.getpid(),"machineId",configurations["machineId"])
			sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",0,"machineId",configurations["machineId"])
		except Exception as e:
			if str(e).find('Lost connection to MySQL server') != -1:
				sqliteDb.reconnectDatabase()
			else:
				logger.errorLog("ERROR-FLFF-065: "+ str(e) )
			pass

		state = True
		while True:
			try:
				data = (self.ser.readline().decode("utf-8"))
				print(type(data))
				# GPIO.output(constant.heartBeatLed, state)
				state = not state
			except Exception as e:
				# print("ERROR- FLR2-002: "+ str(e))
				logger.errorLog("ERROR- FLR2-002: "+ str(e))
				state = False
				# GPIO.output(constant.heartBeatLed, state)
				if self.retry > 20:
					logger.errorLog("ERROR-FLFF-070: "+ str("killing process in 30 Sec") )
					time.sleep(10)
					sqliteDb.updateDataWhereClause("aliveStatusTable","processId",0,"machineId",configurations["machineId"])
					# os.system("sudo reboot")
					os.system("sudo pkill -f quad")
					# os.kill(int(os.getpid()), 9)
				self.retry = self.retry + 1


			print(data , "data")
			logger.debugLog(data)
			if int(len(data)) > 1:
				# data = (data.decode("utf-8"))
				# print(data)
				a = len(data)
				b =((data.find(configurations["data"]["dataSeperator"])))
				# print(b , "b")
				data = (data[b+1:])
				c = data.find(configurations["data"]["dataSeperator"])
				# print(c , "c")
				if b!= -1 and c != -1:
					cncData = data[:c]
					# print(cncData)
					if (cncData[0:2] == "CS"):
						logger.debugLog("cycleStart")
						cycleStartTime = self.configuration.getDateTime()
						self.heartBeatQueue.put({'machineStatus':1})
						# print("cycleStart")
						# print(cycleStartTime)
						flag_cycleStart = 1
						machineStatus = 1
						while machineStatus:
							try:
								# print("cycle started ------------------------------------------------------")
								sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",1,"machineId",configurations["machineId"])
								machineStatus = 0
								break
							except Exception as e:
								logger.errorLog("ERROR- FLR2-003: "+ str(e) )
								if str(e).find('Lost connection to MySQL server') != -1:
									sqliteDb.reconnectDatabase()
								else:
									logger.errorLog("ERROR-FLR2-008: "+ str(e) )
								pass
					elif (cncData[0:2] == "CE"):
						# print(len(cncData) , "   received")
						# print((cncData[3:4]) , "   received")
						if cycleStartTime != None:
							logger.debugLog("cycleEnd")
							# print("cycleEnd")
							cycleEndTime = self.configuration.getDateTime()
							# returnedSec = time_.returnSec(cycleStartTime,cycleEndTime)
							data = {"startDateTime":cycleStartTime,"endDateTime":cycleEndTime}
							# print(data)
							rawData.update(data)
							current_tool = 1
							try:
								data = {"stationNo":str(int(cncData[3:4]))}
								rawData.update(data)
							except:
								logger.debugLog("INFO-FLR2-008: "+ str("stationNo 1 default updated.") )
								data = {"stationNo":"1"}
								rawData.update(data)
								pass
							# print(rawData)
							self.heartBeatQueue.put({'machineStatus':0})
						else:
							pass
							# print("Cycle Start Not received")
					elif (cncData[0:2] == "PC"):
						# print("part Count")
						if cycleStartTime != None:
							res = [int(i) for i in cncData.split() if i.isdigit()] 
							partCount = int(res[0]) + 1
							rawData.update({"actualCount":partCount})
							# print(rawData)
							flag_cycleComplete = 1
							cycleStartTime = None
							cycleEndTime = None
					elif (cncData[0:2] == "CT"):
						# print("Cycle Time")
						if cycleStartTime != None:
							res = [int(i) for i in cncData.split() if i.isdigit()] 
							cycleTime = int(res[0])
							# rawData.update(({"actualCycleTime":cycleTime/1000}))
					elif (cncData[0:2] == "TC"):
						# print("Tool Chnage")
						if cycleStartTime != None:
							current_tool = cncData
							# print(current_tool)
					elif (cncData[0:2] == "PN"):
						# print("Prog Name")
						if cycleStartTime != None:
							res = cncData.split(" ")
							# print(res , "res")
							progNo = res[1]
							# print(str(progNo) + "-----------------")
							rawData.update(({"partId":progNo}))		
					else:
						# pass
						logger.errorLog("ERROR- FLR2-007 : Command Not Found ==> "+str(cncData))
						# print("ERROR- FLR2-007 : Command Not Found ==> "+str(cncData))

						# print('----------------------------------------------------------------------------------------')
						# print(cncData)
						# print('----------------------------------------------------------------------------------------')
						# print('NO DATA STRING FOUND')
					if flag_cycleStart == 1 :
						if current_tool != prev_tool:
							if prev_tool == 0:
								tool_sTime = self.configuration.getDateTime()
								flag_tooling = 1
								prev_tool = current_tool
							else:
								tool_raw_data = {"name": str(prev_tool), "startDateTime":tool_sTime,"endDateTime":self.configuration.getDateTime(), "type":"Tools", "number": toolNo}
								tool_raw_list.append(tool_raw_data)
								flag_tooling = 0
								tool_sTime = self.configuration.getDateTime()
								prev_tool = current_tool
								toolNo = toolNo + 1
					# print(flag_cycleComplete)
					if flag_cycleComplete == 1:
						if flag_tooling == 1:
							tool_raw_data = {"name": str(prev_tool), "startDateTime":cycleStartTime,"endDateTime":cycleEndTime, "type":"Tools", "number": toolNo}
							tool_raw_list.append(tool_raw_data)
							flag_tooling = 0
						toolRaw = {"steps":tool_raw_list}
						rawData.update(toolRaw)
						typeof = "Prod"
						basic = {
								"dataId":self.configuration.getDataId(),
								"machineId":configurations["machineId"],
								"type": constant.cycleTime_type
								}
						rawData.update(basic)
						# jsonBuffer = json.dumps(rawData)
						# print(rawData["startDateTime"])
						# print(rawData["endDateTime"])
						returnedSec = self.configuration.returnSec(rawData["startDateTime"],rawData["endDateTime"])
						# print(returnedSec , "returnedSec")
						# print(self.minThreshold)
						# print(self.maxThreshold)
						if float(self.minThreshold) < float(returnedSec) and float(returnedSec) < float(self.maxThreshold) :
							quadEngine.cycletimeQueue.put(rawData)
							logger.errorLog(rawData)
							try:
								logger.debugLog({"startDateTime":rawData["startDateTime"],
												"endDateTime":rawData["endDateTime"],
												"actualCount":rawData["actualCount"],
												"partId": rawData["partId"],
												"machineId":rawData["machineId"],
												"stationNo":rawData["stationNo"],
												"STEP_len":len(rawData["steps"])
											} , rawData["machineId"])
							except Exception as e:
								logger.errorLog("ERROR-FLR2-009: "+ str(e) )
								logger.debugLog(rawData, rawData["machineId"])
								pass
						else:
							quadEngine.rejectedCycletimeQueue.put(rawData)

						machineStatus = 1
						while machineStatus:
							try:
								sqliteDb.updateDataWhereClause("aliveStatusTable","cycleStatus",0,"machineId",configurations["machineId"])
								machineStatus = 0
								break
							except Exception as e:
								logger.errorLog("ERROR- FLR2-004: "+ str(e) )
								if str(e).find('Lost connection to sqLite3 server') != -1:
									sqliteDb.reconnectDatabase()
								else:
									logger.errorLog("ERROR-FLR2-006: "+ str(e) )
								pass
						prev_tool = 0 
						flag_cycleComplete = 0
						flag_cycleStart = 0
						rawData = {}
						tool_raw_list = []
						current_tool = 0
						toolNo = 1
				else:
					logger.errorLog("ERROR- FLR2-005 :  dataSeperator Not found in received data ==> "+str(data))
					print("dataSeperator Not found in received data ==> "+str(data))
#---------------------