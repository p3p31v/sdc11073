from __future__ import annotations

import decimal
import json
import logging.config
import os
import pathlib
import time
import traceback
import uuid
from typing import TYPE_CHECKING

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
from LED_control import LEDConnectorProviderRole

if TYPE_CHECKING:
    pass

USE_REFERENCE_PARAMETERS = True


def get_network_adapter() -> network.NetworkAdapter:
    """Get network adapter from environment or first loopback."""
    if (ip := os.getenv('ref_ip')) is not None:  # noqa: SIM112
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
    #ws_discovery = ws_discovery or wsdiscovery.WSDiscovery(get_network_adapter().ip)
    ws_discovery = wsdiscovery.WSDiscovery(ip_address = "10.0.10.2")
    ws_discovery.start()
   # print('hola')
    #encendido = ['win&T=1']
   # print(ws_discovery.publish_service(x_addrs=encendido, epr=None, scopes=None, types=None))
   # print('adios')
    dpws_model = dpws_model or ThisModelType(manufacturer='sdc11073',
                                             manufacturer_url='www.sdc11073.com',
                                             model_name='TestDevice',
                                             model_number='1.0',
                                             model_url='www.draeger.com/model',
                                             presentation_url='www.draeger.com/model/presentation')
    dpws_device = dpws_device or ThisDeviceType(friendly_name='TestDevice',
                                                firmware_version='Version1',
                                                serial_number='12345')
    mdib = ProviderMdib.from_mdib_file(str(mdib_path or pathlib.Path(__file__).parent.joinpath('C:/Users/iccas/Python_Projekte/sdc11073/examples/ReferenceTest/reference_mdib.xml')))
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

#probably can be deleted
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
    #wsd = wsdiscovery.WSDiscovery(get_network_adapter().ip)
    wsd = wsdiscovery.WSDiscovery(ip_address = "10.0.10.2")
    wsd.start()

    if USE_REFERENCE_PARAMETERS:
        specific_components = SdcProviderComponents(
            subscriptions_manager_class={'StateEvent': SubscriptionsManagerReferenceParamAsync},
            services_factory=mk_all_services_except_localization,
        )
    else:
        specific_components = None  # provComponents(services_factory=mk_all_services_except_localization)

    prov = create_reference_provider(ws_discovery=wsd, specific_components=specific_components)
    set_reference_data(prov, get_location())


    metric_set = prov.mdib.descriptions.handle.get_one('numeric_Function_Selector.ch0.vmd1')
    metric_set_palette = prov.mdib.descriptions.handle.get_one('numeric_palette.ch0.vmd1')
    metric_set_brightness = prov.mdib.descriptions.handle.get_one('numeric_brightness.ch0.vmd1')
    metric_set_speed = prov.mdib.descriptions.handle.get_one('numeric_Effect_Speed.ch0.vmd1')
    metric_set_intensity = prov.mdib.descriptions.handle.get_one('numeric_Effect_Intensity.ch0.vmd1')
    metric_set_selector = prov.mdib.descriptions.handle.get_one('numeric_Function_Selector.ch0.vmd1')

    string_metric_set = prov.mdib.descriptions.handle.get_one('enumstring.ch0.vmd1')
    string1_metric_set = prov.mdib.descriptions.handle.get_one('string.ch0.vmd1')
    string2_metric_set = prov.mdib.descriptions.handle.get_one('string_2.ch0.vmd1')
    string3_metric_set = prov.mdib.descriptions.handle.get_one('string_3.ch0.vmd1')

    value_operation = prov.mdib.descriptions.handle.get_one('numeric_Function_Selector.ch0.vmd1_sco_0')
    string_operation = prov.mdib.descriptions.handle.get_one('enumstring.ch0.vmd1_sco_0')
    #change the handle and write something that identifies the handle metric names


    print("handle list:")
    numeric_metric_list = []
    for i in prov.mdib.descriptions.handle:
        if i.startswith('numeric') and i.endswith('vmd1') or i.startswith('string') and i.endswith('vmd1') or i.startswith('enumstring') and i.endswith('vmd1'):
            print(i)
            numeric_metric_list.append(i)
    #output
    #enumstring.ch0.vmd1
    #string.ch0.vmd1
    #string_2.ch0.vmd1
    #string_3.ch0.vmd1

    with prov.mdib.transaction_manager() as mgr:
        state = mgr.get_state(value_operation.OperationTarget)
        if not state.MetricValue:
            state.mk_metric_value()
        state = mgr.get_state(string_operation.OperationTarget)
        if not state.MetricValue:
            state.mk_metric_value()


    print("Running forever, CTRL-C to exit")
    #LEDConnectorProviderRole()._controlLedOperation(Schalter_state)
    #LEDConnectorProviderRole()._LED_Effect_Index(Effect_Index=led_effect)
    try:
        current_value = 1
        while True:
            try:
                with prov.mdib.transaction_manager() as mgr:
                    #aqui puedo definir metric_state con numeric_metric_list y asociarlo a la string_metric_set o numeric_metric_set que quiera
                    state = mgr.get_state(metric_set.Handle)

                   
                    if not state.MetricValue:
                        state.mk_metric_value()

                    #state.MetricValue.Value = decimal.Decimal(current_value)
                    print("hola")
                    Control_metric = state.MetricValue.Value
                    #we get the value of the handle for the option to get the state of user desired metric
                    state_general=mgr.get_state(prov.mdib.descriptions.handle.get_one(numeric_metric_list[int(Control_metric)]).Handle)
                    if not state_general.MetricValue:
                        state_general.mk_metric_value()

                    input_metric = state_general.MetricValue.Value

                    try:
                        led_connector = LEDConnectorProviderRole()
                        led_connector._selectOperation(Control_metric, input_metric)
                    except Exception as error:
                        print("No value assigned to the metric", type(error).__name__)

                    print(state.MetricValue.Value)
                    print(state_general.MetricValue.Value)
                    print("adios")


                    #current_value += 1
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
