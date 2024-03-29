from __future__ import annotations
import re
import decimal
import json
import logging.config
import os
import pathlib
import time
import traceback
import uuid
from typing import TYPE_CHECKING
import sdc11073
import sdc11073.certloader
from sdc11073 import location, network, provider, wsdiscovery
from sdc11073.certloader import mk_ssl_contexts_from_folder
from sdc11073.loghelper import LoggerAdapter
from sdc11073.mdib import ProviderMdib
from sdc11073.provider.components import SdcProviderComponents
from sdc11073.provider.servicesfactory import DPWSHostedService, HostedServices, mk_dpws_hosts
from sdc11073.provider.subscriptionmgr_async import SubscriptionsManagerReferenceParamAsync
from sdc11073.xml_types import dpws_types, pm_types
from sdc11073.xml_types import pm_qnames as pm
from sdc11073.xml_types.dpws_types import ThisDeviceType, ThisModelType
from sdc11073.wsdiscovery import WSDiscoverySingleAdapter
from sdc11073.roles.metricprovider import GenericMetricProvider
from sdc11073.provider.porttypes import setserviceimpl
from sdc11073.provider.porttypes import porttypebase
from sdc11073.provider.porttypes.porttypebase import DPWSPortTypeBase

if TYPE_CHECKING:
    pass

USE_REFERENCE_PARAMETERS = True

#easybell DSL-DK3G
#easybell DSL-DK3G
def get_network_adapter() -> network.NetworkAdapter:
    """Get network adapter from environment or first loopback."""
    if (ip := "10.0.10.3") is not None:  # noqa: SIM112 # if (ip := os.getenv('rec_ip'))
        return network.get_adapter_containing_ip(ip)
    # get next available loopback adapter
    return next(adapter for adapter in network.get_adapters() if adapter.is_loopback)


def get_location() -> location.SdcLocation:
    """Get location from environment or default."""
    return location.SdcLocation(fac=os.getenv('ref_fac', default='r_fac'),  # noqa: SIM112
                                poc=os.getenv('ref_poc', default='r_poc'),  # noqa: SIM112
                                bed=os.getenv('ref_bed', default='r_bed'))  # noqa: SIM112


def get_ssl_context() -> sdc11073.certloader.SSLContextContainer | None:
    """Get ssl context from environment or None."""
    if (ca_folder := os.getenv('ref_ca')) is None:  # noqa: SIM112
        return None
    return mk_ssl_contexts_from_folder(ca_folder,
                                       private_key='user_private_key_encrypted.pem',
                                       certificate='user_certificate_root_signed.pem',
                                       ca_public_key='root_certificate.pem',
                                       cyphers_file=None,
                                       ssl_passwd=os.getenv('ref_ssl_passwd'))  # noqa: SIM112


def get_epr() -> uuid.UUID:
    """Get epr from environment or default."""
    if (epr := os.getenv('ref_search_epr')) is not None:  # noqa: SIM112
        return uuid.UUID(epr)
    return uuid.UUID('12345678-6f55-11ea-9697-123456789abc')


def create_reference_provider(
        ws_discovery: wsdiscovery.WSDiscovery | None = None,
        mdib_path: pathlib.Path | None = None,
        dpws_model: dpws_types.ThisModelType | None = None,
        dpws_device: dpws_types.ThisDeviceType | None = None,
        epr: uuid.UUID | None = None,
        specific_components: SdcProviderComponents | None = None,
        ssl_context_container: sdc11073.certloader.SSLContextContainer | None = None) -> provider.SdcProvider:
    # generic way to create a device, this what you usually do:
    ws_discovery = ws_discovery or wsdiscovery.WSDiscovery(get_network_adapter().ip)
    #ws_discovery = WSDiscoverySingleAdapter("VPN - VPN Client")
    #ws_discovery = WSDiscoverySingleAdapter("WLAN")
    #ws_discovery = WSDiscoverySingleAdapter("VPN - VPN Client")
    #ws_discovery = WSDiscoverySingleAdapter("WLAN")
    ws_discovery.start()
    dpws_model = dpws_model or ThisModelType(manufacturer='sdc11073',
                                             manufacturer_url='www.sdc11073.com',
                                             model_name='TestDevice',
                                             model_number='1.0',
                                             model_url='www.draeger.com/model',
                                             presentation_url='www.draeger.com/model/presentation')
    dpws_device = dpws_device or ThisDeviceType(friendly_name='TestDevice',
                                                firmware_version='Version1',
                                                serial_number='12345')
    mdib = ProviderMdib.from_mdib_file(str(mdib_path or pathlib.Path(__file__).parent.joinpath('reference_mdib.xml')))
    prov = provider.SdcProvider(
        ws_discovery=ws_discovery,
        this_model=dpws_model,
        this_device=dpws_device,
        device_mdib_container=mdib,
        epr=epr or get_epr(),
        specific_components=specific_components,
        ssl_context_container=ssl_context_container or get_ssl_context(),
    )
    for desc in prov.mdib.descriptions.objects:
        desc.SafetyClassification = pm_types.SafetyClassification.MED_A
    prov.start_all(start_rtsample_loop=False)
    return prov


def set_reference_data(prov: provider.SdcProvider, loc: location.SdcLocation = None):
    loc = loc or get_location()
    prov.set_location(loc, [pm_types.InstanceIdentifier('Validator', extension_string='System')])
    patient_handle = prov.mdib.descriptions.NODETYPE.get_one(pm.PatientContextDescriptor).Handle
    with prov.mdib.transaction_manager() as mgr:
        patient_state = mgr.mk_context_state(patient_handle)
        patient_state.CoreData.Givenname = "Given"
        patient_state.CoreData.Middlename = ["Middle"]
        patient_state.CoreData.Familyname = "Familiy"
        patient_state.CoreData.Birthname = "Birthname"
        patient_state.CoreData.Title = "Title"
        patient_state.ContextAssociation = pm_types.ContextAssociation.ASSOCIATED
        patient_state.Identification = []


def mk_all_services_except_localization(prov: provider.SdcProvider,
                                        components: SdcProviderComponents,
                                        subscription_managers: dict) -> HostedServices:
    # register all services with their endpoint references acc. to structure in components
    dpws_services, services_by_name = mk_dpws_hosts(prov, components, DPWSHostedService, subscription_managers)
    return HostedServices(dpws_services,
                          services_by_name['GetService'],
                          set_service=services_by_name.get('SetService'),
                          context_service=services_by_name.get('ContextService'),
                          description_event_service=services_by_name.get('DescriptionEventService'),
                          state_event_service=services_by_name.get('StateEventService'),
                          waveform_service=services_by_name.get('WaveformService'),
                          containment_tree_service=services_by_name.get('ContainmentTreeService'))


def setup_logging() -> logging.LoggerAdapter:
    default = pathlib.Path(__file__).parent.joinpath('logging_default.json')
    if default.exists():
        logging.config.dictConfig(json.loads(default.read_bytes()))
    if (extra := os.getenv('ref_xtra_log_cnf')) is not None:  # noqa: SIM112
        logging.config.dictConfig(json.loads(pathlib.Path(extra).read_bytes()))
    return LoggerAdapter(logging.getLogger('sdc'))


def run_provider():
    logger = setup_logging()

    adapter = get_network_adapter()
    wsd = wsdiscovery.WSDiscoverySingleAdapter("VPN - VPN Client")
    
    #wsd = WSDiscoverySingleAdapter("WiFi")
    #wsd = WSDiscoverySingleAdapter("WLAN")
    wsd.start()

    #if USE_REFERENCE_PARAMETERS:
        #specific_components = SdcProviderComponents(
            #subscriptions_manager_class={'StateEvent': SubscriptionsManagerReferenceParamAsync},
            #services_factory=mk_all_services_except_localization,
        #)
    #else:
    specific_components = None  # provComponents(services_factory=mk_all_services_except_localization)
    #if USE_REFERENCE_PARAMETERS:
        #specific_components = SdcProviderComponents(
            #subscriptions_manager_class={'StateEvent': SubscriptionsManagerReferenceParamAsync},
            #services_factory=mk_all_services_except_localization,
        #)
    #else:
    specific_components = None  # provComponents(services_factory=mk_all_services_except_localization)

    prov = create_reference_provider(ws_discovery=wsd, specific_components=specific_components)
    set_reference_data(prov, get_location())

    metric = prov.mdib.descriptions.handle.get_one('Real_time.ch0.vmd0')
    numeric_metric = prov.mdib.descriptions.handle.get_one('numeric.ch0.vmd1')
    alert_condition = prov.mdib.descriptions.handle.get_one('ac0.mds0')
    value_operation = prov.mdib.descriptions.handle.get_one('numeric.ch0.vmd1_sco_0')
    string_operation = prov.mdib.descriptions.handle.get_one('enumstring.ch0.vmd1_sco_0')
    # Define una función para extraer el número de 'ch' en el DescriptorHandle
    def extract_ch_number(item):
        match = re.search(r'ch(\d+)', item.DescriptorHandle)
        if match:
            return int(match.group(1))
        return 0

    with prov.mdib.transaction_manager() as mgr:
        state = mgr.get_state(value_operation.OperationTarget)
        if not state.MetricValue:
            state.mk_metric_value()
        state = mgr.get_state(string_operation.OperationTarget)
        if not state.MetricValue:
            state.mk_metric_value()
    all_metric_descrs = [c for c in prov.mdib.descriptions.objects if c.NODETYPE == pm.NumericMetricDescriptor]
    print("Running forever, CTRL-C to exit")
    mdibData = sdc11073.mdib.providermdib.ProviderMdib.from_mdib_file(pathlib.Path(__file__).parent.joinpath('C:/Users/Jose/Documents/Python_Projekte/sdc11073/examples/ReferenceTest/reference_mdib_original.xml'))
    versions=[]
    versions_old=[]
    handle_update=[]
    try:
        current_value = 0
        while True:
            try:
                with prov.mdib.transaction_manager() as mgr:
                    handle_update=[]
                    
                    state = mgr.get_state(numeric_metric.Handle)
                    #state_array = mgr.get_state(metric.Handle)

                    source_mds_value = dir(state)
                   
                    # here the key
                    print("begin")
                    
                    sorted_output = sorted(prov.mdib.states.NODETYPE.get(pm.NumericMetricState), key=extract_ch_number)
                    print(sorted_output)
                    print("end")
                    #print(prov.mdib.states.NODETYPE.get(pm.NumericMetricState)[0])
                    #new_transaction_versions=prov.mdib.states.handle_version_lookup
                    #older_transaction_versions=prov.mdib.states.handle_version_lookup
                    print(versions_old)
                    versions=[]
                    
                    print(prov.mdib.states.NODETYPE.get(pm.NumericMetricState)[0])
                    #2 es el numero de metricas
                    for i in range(0,2):
                        sorted_output[i].StateVersion
                        versions.append(sorted_output[i].StateVersion)
                        print(prov.mdib.states.NODETYPE.get(pm.NumericMetricState)[i])
                    print("versions",versions)
                    print("versions_old",versions_old)
                    substraction= [v - v_old for v, v_old in zip(versions, versions_old)]
                    contador=0
                    print("substraction",substraction)
                    for i in substraction:
                        
                        if i>0:
                            handle_update.append(sorted_output[contador].DescriptorHandle)
                        contador+=1
                    print("handle update", handle_update)
                            
                    print(prov.mdib.states.NODETYPE.get(pm.NumericMetricState)[0].StateVersion)
                    versions_old=versions
                    
                    print(mgr.metric_state_updates)
                    print(mgr.rt_sample_state_updates)
                    print(mgr.operational_state_updates)


                    #porttypebase.ServiceWithOperations(DPWSPortTypeBase.__init__(sdc_device="mdib", self=self))
                    #setserviceimpl()

                    

                    #if not state_array.MetricValue:
                        #state_array.mk_metric_value()
                    if not state.MetricValue:
                        state.mk_metric_value()
                    #state_array.MetricValue.Samples.append(decimal.Decimal(current_value))
                    state.MetricValue.Value=state.MetricValue.Value + decimal.Decimal(current_value)
                    #print(type(state_array.MetricValue.Samples))
                    #logger.info(f'Set pm:MetricValue/@Samples={state_array.MetricValue.Samples} of the metric with the handle '
                                #f'"{metric.Handle}".')
                    print(type(state.MetricValue.Value))
                    logger.info(f'Set pm:MetricValue/@Value={state.MetricValue.Value} of the metric with the handle '
                                f'"{numeric_metric.Handle}".')
                    #state_array.MetricValue.Samples.append(decimal.Decimal(current_value))
                    state.MetricValue.Value=state.MetricValue.Value + decimal.Decimal(current_value)
                    #print(type(state_array.MetricValue.Samples))
                    #logger.info(f'Set pm:MetricValue/@Samples={state_array.MetricValue.Samples} of the metric with the handle '
                                #f'"{metric.Handle}".')
                    print(type(state.MetricValue.Value))
                    logger.info(f'Set pm:MetricValue/@Value={state.MetricValue.Value} of the metric with the handle '
                                f'"{numeric_metric.Handle}".')
                    current_value += 1
            except Exception:  # noqa: BLE001
                logger.error(traceback.format_exc())
            try:
                with prov.mdib.transaction_manager() as mgr:
                    state = mgr.get_state(alert_condition.Handle)
                    state.Presence = not state.Presence
                    logger.info(f'Set @Presence={state.Presence} of the alert condition with the handle '
                                f'"{alert_condition.Handle}".')
            except Exception:  # noqa: BLE001
                logger.error(traceback.format_exc())
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping provider...")
        prov.stop_all()
        print("Stopping discovery...")
        wsd.stop()


if __name__ == '__main__':
    run_provider()
