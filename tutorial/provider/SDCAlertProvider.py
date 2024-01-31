import os
import uuid
import sys

import sdc11073
from sdc11073.namespaces import domTag
from sdc11073.sdcdevice import SdcDevice
from sdc11073.wsdiscovery import WSDiscoverySingleAdapter

from Client.CustomProductRole import CustomProductRole


class SDCAlertProvider:

    def __init__(self, args, workingDir):
        self.m_programArguments = args
        self.m_workingDir = workingDir
        self.m_parameterDict = {}
        self.processParameterArgs()

    def processParameterArgs(self):
        print(self.m_workingDir + "/Parameter/" + self.m_programArguments.parameter)
        file = open(self.m_workingDir + "/Parameter/" + self.m_programArguments.parameter)
        # file = open(self.m_workingDir + "/Parameter/Test.txt", "r")
        puffer = file.read()
        parameterList = puffer.split(" ")
        self.m_parameterDict = {"BaseUUID": parameterList[0], "deviceUUID": parameterList[1],
                                "manufacturer": parameterList[2], "modelName": parameterList[3],
                                "friendlyName": parameterList[4], "serialNumber": parameterList[5],
                                "patientVorname": parameterList[6],
                                "patientNachname": parameterList[7], "MDIBName": parameterList[8],
                                "Facility": parameterList[9], "PoC": parameterList[10], "Bed": parameterList[11]}

    def startSDCProvider(self):
        print("Preparing SDC Provider")

        mdibPath = os.path.join(self.m_workingDir + "/MDIBs/", self.m_parameterDict["MDIBName"])

        baseUUID = uuid.UUID(self.m_parameterDict["BaseUUID"])
        deviceUUID = uuid.uuid5(baseUUID, self.m_parameterDict["deviceUUID"])
        discoveryService = WSDiscoverySingleAdapter("Ethernet")
        discoveryService.start()
        print("SDC Discovery gestartet")
        print("UUID: " + deviceUUID.hex)

        ref_fac = os.getenv('ref_fac') or self.m_parameterDict["Facility"]
        ref_poc = os.getenv('ref_poc') or self.m_parameterDict["PoC"]
        ref_bed = os.getenv('ref_bed') or self.m_parameterDict["Bed"]

        mdibData = sdc11073.mdib.DeviceMdibContainer.fromMdibFile(mdibPath)
        locationData = sdc11073.location.SdcLocation(ref_fac, ref_poc, ref_bed)

        dpwsModel = sdc11073.pysoap.soapenvelope.DPWSThisModel(manufacturer=self.m_parameterDict["manufacturer"],
                                                               manufacturerUrl='www.iccas.de',
                                                               modelName=self.m_parameterDict["modelName"],
                                                               modelNumber='1.0',
                                                               modelUrl='www.gibts.net',
                                                               presentationUrl='www.sdc11073.com/model/presentation')

        dpwsDevice = sdc11073.pysoap.soapenvelope.DPWSThisDevice(friendlyName=self.m_parameterDict["friendlyName"],
                                                                 firmwareVersion='Version2',
                                                                 serialNumber=self.m_parameterDict["serialNumber"])
        # Device Initialising -- Implementierung von Speziellen Device Verhalten
        my_product_impl = CustomProductRole(log_prefix='p1')

        sdcDeviceObject = SdcDevice(ws_discovery=discoveryService,
                                    my_uuid=deviceUUID,
                                    model=dpwsModel,
                                    device=dpwsDevice,
                                    deviceMdibContainer=mdibData,
                                    roleProvider= my_product_impl)

        sdcDeviceObject.startAll()
        validators = [sdc11073.pmtypes.InstanceIdentifier('Validator', extensionString='System')]
        sdcDeviceObject.setLocation(locationData, validators)

        # Set Patientendaten
        patientDescriptorHandle = mdibData.descriptions.nodeName.get(domTag('PatientContext'))[0].handle

        with mdibData.mdibUpdateTransaction() as mgr:
            patientContainer = mgr.getContextState(patientDescriptorHandle)
            patientContainer.Givenname = self.m_parameterDict["patientVorname"]
            patientContainer.Familyname = self.m_parameterDict["patientNachname"]
            patientContainer.ContextAssociation = "Assoc"
            # TODO Was ist das hier? Was könnte da drin stehen? Tags?
            identifiers = []
            patientContainer.Identification = identifiers

        # legt eine Liste mit Descriptoren an, die später für die Metriken gebraucht werden
        description = list(sdcDeviceObject.mdib.descriptions.objects)
        description.sort(key=lambda x: x.handle)
        metric = None

        print("Running forever, CTRL-C to  exit")
        try:
            """
            x = 0
            while x < 10000:
                x += 1
                print("NYI")

            print("Wartete genug. Programm beendet")
            """
            while True:
                # TODO Implement Stuff
                pass

        except KeyboardInterrupt:
            sdcDeviceObject.stopAll()
            sys.exit(0)
            print("Exiting...")
