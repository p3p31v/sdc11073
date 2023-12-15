import os
import time
import traceback
from collections import defaultdict
from concurrent import futures
from decimal import Decimal
from sdc11073 import commlog, observableproperties
from sdc11073.certloader import mk_ssl_contexts_from_folder
from sdc11073.consumer import SdcConsumer
from sdc11073.definitions_sdc import SdcV1Definitions
from sdc11073.mdib.consumermdib import ConsumerMdib
from sdc11073.mdib.consumermdibxtra import ConsumerMdibMethods
from sdc11073.wsdiscovery import WSDiscovery
from sdc11073.xml_types.msg_types import InvocationState

ConsumerMdibMethods.DETERMINATIONTIME_WARN_LIMIT = 2.0

adapter_ip = os.getenv('ref_ip') or '127.0.0.1'
ca_folder = os.getenv('ref_ca')
ssl_passwd = os.getenv('ref_ssl_passwd') or None
search_epr = os.getenv('ref_search_epr') or 'abc'
ENABLE_COMMLOG = True

def run_ref_test():
    results = []
    print(f'using adapter address {adapter_ip}')
    print(f'Test step 1: discover device with endpoint ending with "{search_epr}"')
    wsd = WSDiscovery(ip_address="10.0.10.2")
    wsd.start()
    my_service = next((s for s in wsd.search_services(types=SdcV1Definitions.MedicalDeviceTypesFilter) if s.epr.endswith(search_epr)), None)
    
    if my_service:
        print('found service {}'.format(my_service.epr))
        print('Test step 1 successful: device discovered')
        results.append('### Test 1 ### passed')
    else:
        print('Test step 1 failed: device not found')
        results.append('### Test 1 ### failed')
        return results

    print('Test step 2: connect to device...')
    try:
        ssl_context_container = mk_ssl_contexts_from_folder(ca_folder, cyphers_file=None, private_key='user_private_key_encrypted.pem', certificate='user_certificate_root_signed.pem', ca_public_key='root_certificate.pem', ssl_passwd=ssl_passwd) if ca_folder else None
        client = SdcConsumer.from_wsd_service(my_service, ssl_context_container=ssl_context_container, validate=True)
        client.start_all()
        print('Test step 2 successful: connected to device')
        results.append('### Test 2 ### passed')
    except Exception as ex:
        print(f'Test 2: {ex}')
        results.append('### Test 2 ### failed')
        return results

    print('Test step 3&4: get mdib and subscribe...')
    try:
        mdib = ConsumerMdib(client)
        mdib.init_mdib()
        print('Test step 3&4 successful')
        results.append('### Test 3 ### passed')
        results.append('### Test 4 ### passed')
    except Exception as ex:
        print(f'Test 3&4: {ex}')
        results.append('### Test 3 ### failed')
        results.append('### Test 4 ### failed')
        return results

    while True:
        Function_selector = input("write the number for the function you want to select")
        schalter_value = input("write the value for the function you want to select")
        pm = mdib.data_model.pm_names
        print('Test step 5: check that at least one patient context exists')
        patients = mdib.context_states.NODETYPE.get(pm.PatientContextState, [])
        if patients:
            print(f'found {len(patients)} patients, Test step 5 successful')
            results.append('### Test 5 ### passed')
        else:
            print('found no patients, Test step 5 failed')
            results.append('### Test 5 ### failed')

        print('Test step 6: check that at least one location context exists')
        locations = mdib.context_states.NODETYPE.get(pm.LocationContextState, [])
        if locations:
            print(f'found {len(locations)} locations, Test step 6 successful')
            results.append('### Test 6 ### passed')
        else:
            print('found no locations, Test step 6 failed')
            results.append('### Test 6 ### failed')

        print('Test step 7&8: count metric state updates and alert state updates')
        metric_updates = defaultdict(list)
        alert_updates = defaultdict(list)

        def onMetricUpdates(metricsbyhandle):
            print('onMetricUpdates', metricsbyhandle)
            for k, v in metricsbyhandle.items():
                metric_updates[k].append(v)

        observableproperties.bind(mdib, metrics_by_handle=onMetricUpdates)

        sleep_timer = 20
        min_updates = sleep_timer // 5 - 1
        print(f'will wait for {sleep_timer} seconds now, expecting at least {min_updates} updates per Handle')
        time.sleep(sleep_timer)
        print(metric_updates)
        print(alert_updates)
        
        if not metric_updates:
            results.append('### Test 7 ### failed')
        else:
            for k, v in metric_updates.items():
                if len(v) < min_updates:
                    print(f'found only {len(v)} updates for {k}, test step 7 failed')
                    results.append(f'### Test 7 Handle {k} ### failed')
                else:
                    print(f'found {len(v)} updates for {k}, test step 7 ok')
                    results.append(f'### Test 7 Handle {k} ### passed')
        if int(Function_selector) <= 4:
            print('Test step 9: call SetValue operation')
            set_operations = mdib.descriptions.NODETYPE.get(pm.SetValueOperationDescriptor, [])
        elif int(Function_selector) > 4:
            print('Test step 9: call SetString operation')
            set_operations = mdib.descriptions.NODETYPE.get(pm.SetStringOperationDescriptor, [])
        else:
            print(f'Invalid input for Function_selector: {Function_selector}')
            results.append('### Test 9 ### failed')
            time.sleep(5)
            continue  # Skip the rest of the loop

        # Common code for both cases
        operation_type = 'SetValue' if int(Function_selector) <= 4 else 'SetString'

        if not set_operations:
            print(f'Test step 9 failed, no {operation_type} operation found')
            results.append(f'### Test 9 ### failed')
        else:
            for s in set_operations:
                print(f'{operation_type} Op = {s}')
                try:
                    if operation_type == 'SetValue':
                        fut = client.set_service_client.set_numeric_value(s.Handle, Decimal(int(schalter_value)))
                    else:  # operation_type == 'SetString'
                        fut = client.set_service_client.set_string(s.Handle, schalter_value)

                    fut_selector = client.set_service_client.set_numeric_value('numeric_Function_Selector.ch0.vmd1_sco_0', Decimal(int(Function_selector)))

                    try:
                        res = fut.result(timeout=10)
                        res_selector = fut_selector.result(timeout=10)

                        if res.InvocationInfo.InvocationState != InvocationState.FINISHED:
                            print(f'{operation_type} operation {s.Handle} did not finish with "Fin": {res}')
                            results.append(f'### Test 9({operation_type}) ### failed')
                        else:
                            print(f'{operation_type} operation {s.Handle} ok: {res}')
                            results.append(f'### Test 9({operation_type}) ### passed')

                    except futures.TimeoutError:
                        print('timeout error')
                        results.append(f'### Test 9({operation_type}) ### failed')

                except Exception as ex:
                    print(f'Test 9({operation_type}): {ex}')
                    results.append(f'### Test 9({operation_type}) ### failed')
run_results = run_ref_test()