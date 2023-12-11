import logging
import time
import os
import uuid
from sdc11073.xml_types import pm_types, msg_types
from sdc11073.xml_types import pm_qnames as pm
from sdc11073.xml_types.actions import periodic_actions
from sdc11073.wsdiscovery import WSDiscovery
from sdc11073.definitions_sdc import SdcV1Definitions
from sdc11073.consumer import SdcConsumer
from sdc11073.certloader import mk_ssl_contexts_from_folder
from sdc11073.mdib import ConsumerMdib
from sdc11073 import observableproperties
from sdc11073.loghelper import basic_logging_setup
from decimal import Decimal
from sdc11073.xml_types.msg_types import InvocationState
from concurrent import futures
import requests
# This example shows how to implement a very simple SDC Consumer (client)
# It will scan for SDC Providers and connect to on well known UUID

# The provider we connect to is known by its UUID
# The UUID is created from a base
baseUUID = uuid.UUID('{cc013678-79f6-403c-998f-3cc0cc050230}')
device_A_UUID = uuid.uuid5(baseUUID, "12345")
ca_folder = os.getenv('ref_ca')  # noqa: SIM112
search_epr = os.getenv('ref_search_epr') or 'abc'
ssl_passwd = os.getenv('ref_ssl_passwd') or None  # noqa: SIM112

# callback function that will be called upon metric updates from the provider
def on_metric_update(metrics_by_handle: dict):
    # we get all changed handles as parameter, iterate over them and output
    print(f"Got update on: {list(metrics_by_handle.keys())}")
    for handle, metric in metrics_by_handle.items(): #dict_items([('numeric.ch0.vmd0', NumericMetricStateContainer DescriptorHandle="numeric.ch0.vmd0" StateVersion=260), ('numeric.ch1.vmd0', NumericMetricStateContainer DescriptorHandle="numeric.ch1.vmd0" StateVersion=260), ('numeric.ch0.vmd1', NumericMetricStateContainer DescriptorHandle="numeric.ch0.vmd1" StateVersion=260)])
        print(f"Got update on handle {metric}:")
        print(f"Metric Value: {metric.MetricValue.Value}")
        
        # Access and print specific properties of the metric
        
        # You can access other properties of the metric as needed

        print(metrics_by_handle.items())

def set_ensemble_context(mdib: ConsumerMdib, sdc_consumer: SdcConsumer) -> None:
    # calling operation on remote device 
    print("Trying to set ensemble context of device A")
    # first we get the container to the element in the MDIB
    
    ensemble_descriptor_container = mdib.descriptions.NODETYPE.get_one(pm.EnsembleContextDescriptor)
   # print("Hola")
   # print(ensemble_descriptor_container)#Descriptor "EnsembleContextDescriptor": handle=EN.mds0 descriptor version=0 parent handle=SC.mds0
   # print("adios")
    # get the context of our provider(client)
    context_client = sdc_consumer.context_service_client
    #print("Hola")
    #print(context_client) #ContextServiceClient "{http://standards.ieee.org/downloads/11073/11073-20701-2018}ContextService" endpoint = EndpointReferenceType([('Address', AnyUriTextElement in sub-element {http://www.w3.org/2005/08/addressing}Address), ('ReferenceParameters', <sdc11073.xml_types.xml_structure.AnyEtreeNodeListProperty object at 0x0000019DCFEBEC40>), ('Metadata', <sdc11073.xml_types.xml_structure.AnyEtreeNodeListProperty object at 0x0000019DCFEBEDC0>)])
   # print("adios")
    # start with empty operation handle and try to find the one we need
    operation_handle = None
    # iterate over all matching handles (can be 0..n)
    for op_descr in mdib.descriptions.NODETYPE.get(pm.SetContextStateOperationDescriptor, []):
        if op_descr.OperationTarget == ensemble_descriptor_container.Handle:
            operation_handle = op_descr.Handle
    # now we should have an operation handle to work with
    # create a new ensemble context as parameter to this operation
    new_ensemble_context = context_client.mk_proposed_context_object(ensemble_descriptor_container.Handle)
    new_ensemble_context.ContextAssociation = pm_types.ContextAssociation.ASSOCIATED
    new_ensemble_context.Identification = [
        pm_types.InstanceIdentifier(root="1.2.3", extension_string="SupervisorSuperEnsemble")]
    # execute the remote operation (based on handle) with the newly created ensemble as parameter
    response = context_client.set_context_state(operation_handle, [new_ensemble_context])
    result: msg_types.OperationInvokedReportPart = response.result()
    if result.InvocationInfo.InvocationState not in (msg_types.InvocationState.FINISHED,
                                                     msg_types.InvocationState.FINISHED_MOD):
        print(f'set ensemble context state failed state = {result.InvocationInfo.InvocationState}, '
              f'error = {result.InvocationInfo.InvocationError}, msg = {result.InvocationInfo.InvocationErrorMessage}')
    else:
        print(f'set ensemble context was successful.')


# main entry, will start to scan for the known provider and connect
# runs forever and consumes metrics everafter
if __name__ == '__main__':
    # start with discovery (MDPWS) that is running on the named adapter "Ethernet" (replace as you need it on your machine, e.g. "enet0" or "Ethernet)
    basic_logging_setup(level=logging.INFO)
    #my_discovery = WSDiscovery(ip_address = "10.249.117.79")
    my_discovery = WSDiscovery("127.0.0.1")
    # start the discovery
    my_discovery.start()
    # we want to search until we found one device with this client
    found_device = False
    # loop until we found our provider
    my_service = None
    while my_service is None:
        services =my_discovery.search_services(types=SdcV1Definitions.MedicalDeviceTypesFilter)
        print('found {} services {}'.format(len(services), ', '.join([s.epr for s in services])))
        for s in services:
            if s.epr.endswith(search_epr):
                print('hola')
                my_service = s
                print('found service {}'.format(s.epr))
                break
    print('Test step 1 successful: device discovered')
    if ca_folder:
        ssl_context_container = mk_ssl_contexts_from_folder(ca_folder,
                                                                cyphers_file=None,
                                                                private_key='user_private_key_encrypted.pem',
                                                                certificate='user_certificate_root_signed.pem',
                                                                ca_public_key='root_certificate.pem',
                                                                ssl_passwd=ssl_passwd,
                                                                )
    else:
        ssl_context_container = None
        client = SdcConsumer.from_wsd_service(my_service, ssl_context_container=ssl_context_container, validate=True)

    mdib = ConsumerMdib(client)

    setvalue_operations = mdib.descriptions.NODETYPE.get(pm.SetValueOperationDescriptor, [])

    setval_handle = 'numeric.ch0.vmd1_sco_0'
    print(setval_handle)
    results = []
    if len(setvalue_operations) == 0:
        print('Test step 9 failed, no SetValue operation found')
        results.append('### Test 9(SetValue) ### failed')
    else:
        for s in setvalue_operations:
            if s.Handle != setval_handle:
                continue
            print('setNumericValue Op ={}'.format(s))
            try:
                fut = client.set_service_client.set_numeric_value(s.Handle, Decimal('9'))
                try:
                    res = fut.result(timeout=10)
                    print("hola")
                    print(s.Handle)
                    print("adios")
                    if res.InvocationInfo.InvocationState != InvocationState.FINISHED:
                        print('set value operation {} did not finish with "Fin":{}'.format(s.Handle, res))
                    else:
                        print('set value operation {} ok:{}'.format(s.Handle, res))
                        results.append('### Test 9(SetValue) ### passed')
                except futures.TimeoutError:
                    print('timeout error')
                    results.append('### Test 9(SetValue) ### failed')
            except Exception as ex:
                print(f'Test 9(SetValue): {ex}')
                results.append('### Test 9(SetValue) ### failed')
    while not found_device:
        # we now search explicitly for MedicalDevices on the network
        # this will send a probe to the network and wait for responses
        # See MDPWS discovery mechanisms for details
        print('searching for sdc providers')
        services = my_discovery.search_services(types=SdcV1Definitions.MedicalDeviceTypesFilter)
        # now iterate through the discovered services to check if we foundDevice
        # the specific provider we search for
        for one_service in services:
            print("Got service: {}".format(one_service.epr))
            # the EndPointReference is created based on the UUID of the Provider
            if one_service.epr == device_A_UUID.urn:
                print("Got a match: {}".format(one_service))
                # now create a new SDCClient (=Consumer) that can be used
                # for all interactions with the communication partner
                my_client = SdcConsumer.from_wsd_service(one_service, ssl_context_container=None)
                # start all services on the client to make sure we get updates
                my_client.start_all(not_subscribed_actions=periodic_actions)
                # all data interactions happen through the MDIB (MedicalDeviceInformationBase)
                # that contains data as described in the BICEPS standard
                # this variable will contain the data from the provider
                my_mdib = ConsumerMdib(my_client)
                print("inicio")
                print(dir(my_client))
                print("fin")
                my_mdib.init_mdib()
                #url =f"http://10.249.117.79/win&T=0"
                #response = requests.post(url)
                # we can subscribe to updates in the MDIB through the
                # Observable Properties in order to get a callback on
                # specific changes in the MDIB
                observableproperties.bind(my_mdib, metrics_by_handle=on_metric_update)
                # in order to end the 'scan' loop
                found_device = True

                # now we demonstrate how to call a remote operation on the consumer
                set_ensemble_context(my_mdib, my_client)


    # endless loop to keep the client running and get notified on metric changes through callback
    while True:
        time.sleep(1)
