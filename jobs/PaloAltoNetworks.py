import requests
import json
import xmltodict
from nautobot.apps.jobs import Job, register_jobs
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceType, Interface, Location, LocationType, Platform, SoftwareVersion
from nautobot.dcim.choices import InterfaceTypeChoices
from nautobot.tenancy.models import Tenant
from nautobot.ipam.models import IPAddress, Namespace, Prefix
from nautobot.extras.models import Status, Role, Secret
from nautobot.extras.jobs import Job


class FetchAndAddorUpdatePanoramaandFirewall(Job):
    class Meta:
        name = "Fetch, Add and Update Panorama and Firewall objects"
        description = "Fetches devices from Panorama and Firewalls from Nautobot devices tagged with Firewall as a Service updates the objects in Nautobot."

    def run(self):
        #Panorama
        device_type = DeviceType.objects.filter(name="Panorama")
        devices = Device.objects.filter(_custom_field_data={'Services':['Firewall as a Service']}, device_type=device_type)
        self.logger.info(f"{devices}")
        for device in devices:

            device_name_string = str(device.name)
            #self.logger.info(tenant_name_string)
            command = ""
            secret_apikey = Secret.objects.get(name=f"{device_name_string} Panorama").get_values()
            base_url = f'https://{host}/api/?type=op&key=${secret_apikey}&cmd=${command}'
            #headers = {
            #    'Authorization': f'Bearer {secret_apikey}',
            #    'Content-Type': 'application/json'
            #}
            devices = []
            page = 1
            page_size = 100  # Adjust the page size as needed
            while True:
                response = requests.get(f"{base_url}/devices?page={page}&limit={page_size}&views=FULL", headers=headers)
                
                if response.status_code != 200:
                    self.logger.error(f"Error: {response.status_code}")
                    break

                data = response.json()
                devices.extend(data['data'])

                if len(data['data']) < page_size:
                    break  # No more pages to fetch
                page += 1
            for device in devices:
                self.logger.info(f"Fetched Device: {device}")

                # Example of adding a device to Nautobot
                # Adjust the fields according to your device data and Nautobot setup
                device_name = device.get('hostname')
                device_serial = device.get('serial_number')
                device_model = device.get('product_type')
                device_ip = device.get('ip_address')
                device_role = device.get('device_function')
                device_software = device.get('software_version')

                # Fetch or create the necessary related objects
                device_type, _ = DeviceType.objects.get_or_create(model=device_model)

                status = Status.objects.get(name='Active')  # Adjust status as needed
                location_type = LocationType.objects.get(name='Site')
                # Create or fetch location 
                existing_location = Location.objects.filter(name=device["locations"][1]["name"], tenant=tenant_name).first()
                if existing_location:
                    self.logger.info(f"Location in Nautobot: {device["locations"][1]["name"]} already exists")
                else:
                    new_location = Location(
                        name=device["locations"][1]["name"],
                        tenant=tenant_name,
                        location_type=location_type,
                        status=status
                    )
                    new_location.save()
                    self.logger.info(f"Created Location in Nautobot: {device["locations"][1]["name"]}")

                # Check for existing software version
                #existing_software = SoftwareVersion

                # Check for device roles
                if device_role == "SWITCH":
                    role_existing = Role.objects.filter(name="Switch").first()
                elif device_role == "AP":
                    role_existing = Role.objects.filter(name="Accesspoint").first()

                device_location = Location.objects.filter(name=device["locations"][1]["name"], tenant=tenant_name).first()
                # Check for existing device
                existing_device = Device.objects.filter(serial=device_serial).first()
                if existing_device:
                    # Update existing device
                    existing_device.name = device_name
                    existing_device.role = role_existing
                    existing_device.device_type = device_type
                    existing_device.status = status
                    existing_device.location = device_location  # Set the last location as campus
                    existing_device.tenant = tenant_name
                    existing_device.save()
                    self.logger.info(f"Updated Device in Nautobot: {device_name}")
                else:
                    # Create new device
                    nautobot_device = Device(
                        name=device_name,
                        serial=device_serial,
                        role=role_existing,
                        device_type=device_type,
                        tenant=tenant_name,
                        status=status,
                        location=device_location # Set the last location as campus
                    )
                    nautobot_device.save()
                    self.logger.info(f"Added Device to Nautobot: {device_name}")
                # Namespace
                # Update Namespace
                existing_namespace = Namespace.objects.filter(name=tenant_name).first()
                if existing_namespace:
                    existing_namespace.name = tenant_name_string
                    existing_namespace.location = device_location
                    existing_namespace.save()
                    self.logger.info(f"Updated Namespace in Nautobot: {tenant_name}")
                # Create Namespace
                else:
                    new_namespace = Namespace(
                        name=tenant_name_string,
                        location=device_location
                    )
                    new_namespace.save()
                    self.logger.info(f"Created namespace in Nautobot: {tenant_name}")

                #IP Prefix
                device_namespace = Namespace.objects.filter(name=tenant_name).first()
                # 10.0.0.0/8
                existing_prefix = Prefix.objects.filter(network="10.0.0.0",prefix_length="8").first()
                # Update Prefix
                if existing_prefix:
                    existing_prefix.network =  "10.0.0.0"
                    existing_prefix.prefix_length="8"
                    existing_prefix.namepsace = device_namespace
                    existing_prefix.location = device_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 10.0.0.0/8")
                else:
                    new_prefix = Prefix(
                        network="10.0.0.0",
                        prefix_length="8",
                        namespace=device_namespace,
                        location=device_location,
                        tenant=tenant_name,
                        status=status
                    )
                    new_prefix.save()
                    self.logger.info(f"Created Prefix in Nautobot: 10.0.0.0/8")
                    # Add IP address and associate with management interface
                # Add prefix 192.168.0.0/16
                existing_prefix = Prefix.objects.filter(network="192.168.0.0",prefix_length="16").first()
                # Update Prefix
                if existing_prefix:
                    existing_prefix.network =  "192.168.0.0"
                    existing_prefix.prefix_length="16"
                    existing_prefix.namepsace = device_namespace
                    existing_prefix.location = device_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 192.168.0.0/16")
                else:
                    new_prefix = Prefix(
                        network="192.168.0.0",
                        prefix_length="16",
                        namespace=device_namespace,
                        location=device_location,
                        tenant=tenant_name,
                        status=status
                    )
                    new_prefix.save()
                    self.logger.info(f"Created Prefix in Nautobot: 192.168.0.0/16")
                    # Add IP address and associate with management interface

                # Add prefix 172.16.0.0/12
                existing_prefix = Prefix.objects.filter(network="172.16.0.0",prefix_length="12").first()
                # Update Prefix
                if existing_prefix:
                    existing_prefix.network =  "172.16.0.0"
                    existing_prefix.prefix_length="12"
                    existing_prefix.namepsace = device_namespace
                    existing_prefix.location = device_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 172.16.0.0/12")
                else:
                    new_prefix = Prefix(
                        network="172.16.0.0",
                        prefix_length="12",
                        namespace=device_namespace,
                        location=device_location,
                        tenant=tenant_name,
                        status=status
                    )
                    new_prefix.save()
                    self.logger.info(f"Created Prefix in Nautobot: 172.16.0.0/12")
                    # Add IP address and associate with management interface
                existing_ip = IPAddress.objects.filter(host=device_ip, tenant=tenant_name)
                # Update ip
                if existing_ip:
                    self.logger.info(f"IP already exists")
                else:
                    new_ip = IPAddress(
                        host=device_ip,
                        mask_length="32",
                        namespace=device_namespace,
                        tenant=tenant_name,
                        dns_name=device_name,
                        status=status
                    )
                    new_ip.save()
                    self.logger.info(f"Created ip in Nautobot: {device_ip}/32")

                    
                device_object = Device.objects.filter(serial=device_serial).first()
                device_ip_object = IPAddress.objects.filter(host=device_ip, tenant=tenant_name)
                existing_mgmt01 = Interface.objects.filter(device=device_object, name="mgmt01")
                
                if existing_mgmt01:
                    self.logger.info(f"Interface mgmt01 already exists on {device_name} in Nautobot.")
                else:
                    new_mgmt01 = Interface(
                        device=device_object,
                        name="mgmt01",
                        mgmt_only=True,
                        status=status,
                        type=InterfaceTypeChoices.TYPE_VIRTUAL
                    )
                    
                    new_mgmt01.save()
                    new_mgmt01.ip_addresses.set(device_ip_object)
                    
                    self.logger.info(f"Created interface mgmt01 on device {device_name} in Nautobot.")

                # Software
                device_platform= Platform.objects.filter(name="PAN OS").first()
                if device_name.__contains__("SR"):
                    device_platform= Platform.objects.filter(name="Aerohive").first()

                    existing_software=SoftwareVersion.objects.filter(version=device_software).first()

                    if existing_software:
                        self.logger.info(f"Software {device_software} already exists.")

                    else:
                        new_software = SoftwareVersion(
                            version=device_software,
                            platform=device_platform,
                            status=status
                        )
                        new_software.save()
                        self.logger.info(f"Software {device_software} was created in Nautobot.")
                else:
                    device_platform= Platform.objects.filter(name="ExtremeCloudIQ").first()
                    existing_software=SoftwareVersion.objects.filter(version=device_software).first()

                    if existing_software:
                        self.logger.info(f"Software {device_software} already exists.")

                    else:
                        new_software = SoftwareVersion(
                            version=device_software,
                            platform=device_platform,
                            status=status
                        )
                        new_software.save()
                        self.logger.info(f"Software {device_software} was created in Nautobot.")


 

        #Firewall
        device_role = Role.objects.filter(name="Firewall")
        devices_firewall = Device.objects.filter(_custom_field_data={'Services':['Firewall as a Service']}, Role=device_role)

        for device_firewall in devices_firewall:
            device_name_string = str(device_firewall.name)
            device_host = device_firewall.custom_field_data["netsecurity_service_proxy"]
            tenant_name = device_firewall.tenant
            tenant_name_string = str(device_firewall.tenant)
            command =  "<show><system><info></info></system></show>"
            secret_apikey = Secret.objects.get(name=f"{device_name_string} Firewall").get_values()
            base_url = f'https://{device_host}/api/?type=op&key=${secret_apikey}&cmd=${command}'

            response_xml = requests.get(f'https://{device_host}/api/?type=op&key=${secret_apikey}&cmd=${command}')
                
            if response_xml.status_code != 200:
                self.logger.error(f"Error: {response.status_code}")
                break
            
            dict_data = xmltodict.parse(response_xml)
            devices_firewall = json.dumps(dict_data, indent=4)

            firewall_name = device.get('hostname')
            firewall_serial = device.get('serial')
            firewall_model = device.get('model')
            firewall_ip = device.get('ip-address')
            firewall_software = device.get('sw-version')
            firewall_app = device.get('app-version')
            firewall_av = device.get('av-version')
            firewall_wildfire = device.get('wildfire-version')
            firewall_url_filter = device.get('url-filtering-version')
            firewall_threat = device.get('threat-version')
            
            firewall_platform= Platform.objects.filter(name="PAN OS").first()
            existing_software=SoftwareVersion.objects.filter(version=device_software).first()

            if existing_software:
                self.logger.info(f"Software {device_software} already exists.")

            else:
                new_software = SoftwareVersion(
                    version=device_software,
                    platform=device_platform,
                    status=status
                )
                new_software.save()
                self.logger.info(f"Software {device_software} was created in Nautobot.")

            # Namespace
            # Update Namespace
            tenant_name 
            existing_namespace = Namespace.objects.filter(name=tenant_name).first()
            if existing_namespace:
                existing_namespace.name = tenant_name_string
                existing_namespace.location = device_location
                existing_namespace.save()
                self.logger.info(f"Updated Namespace in Nautobot: {tenant_name}")
            # Create Namespace
            else:
                new_namespace = Namespace(
                    name=tenant_name_string,
                    location=device_location
                )
                new_namespace.save()
                self.logger.info(f"Created namespace in Nautobot: {tenant_name}")

            #IP Prefix
            device_namespace = Namespace.objects.filter(name=tenant_name).first()
            # 10.0.0.0/8
            existing_prefix = Prefix.objects.filter(network="10.0.0.0",prefix_length="8").first()
            # Update Prefix
            if existing_prefix:
                existing_prefix.network =  "10.0.0.0"
                existing_prefix.prefix_length="8"
                existing_prefix.namepsace = device_namespace
                existing_prefix.location = device_location
                existing_prefix.tenant = tenant_name
                existing_prefix.status = status
                existing_prefix.save()
                self.logger.info(f"Updated Prefix in Nautobot: 10.0.0.0/8")
            else:
                new_prefix = Prefix(
                    network="10.0.0.0",
                    prefix_length="8",
                    namespace=device_namespace,
                    location=device_location,
                    tenant=tenant_name,
                    status=status
                )
                new_prefix.save()
                self.logger.info(f"Created Prefix in Nautobot: 10.0.0.0/8")
                # Add IP address and associate with management interface
            # Add prefix 192.168.0.0/16
            existing_prefix = Prefix.objects.filter(network="192.168.0.0",prefix_length="16").first()
            # Update Prefix
            if existing_prefix:
                existing_prefix.network =  "192.168.0.0"
                existing_prefix.prefix_length="16"
                existing_prefix.namepsace = device_namespace
                existing_prefix.location = device_location
                existing_prefix.tenant = tenant_name
                existing_prefix.status = status
                existing_prefix.save()
                self.logger.info(f"Updated Prefix in Nautobot: 192.168.0.0/16")
            else:
                new_prefix = Prefix(
                    network="192.168.0.0",
                    prefix_length="16",
                    namespace=device_namespace,
                    location=device_location,
                    tenant=tenant_name,
                    status=status
                )
                new_prefix.save()
                self.logger.info(f"Created Prefix in Nautobot: 192.168.0.0/16")
                # Add IP address and associate with management interface

            # Add prefix 172.16.0.0/12
            existing_prefix = Prefix.objects.filter(network="172.16.0.0",prefix_length="12").first()
            # Update Prefix
            if existing_prefix:
                existing_prefix.network =  "172.16.0.0"
                existing_prefix.prefix_length="12"
                existing_prefix.namepsace = device_namespace
                existing_prefix.location = device_location
                existing_prefix.tenant = tenant_name
                existing_prefix.status = status
                existing_prefix.save()
                self.logger.info(f"Updated Prefix in Nautobot: 172.16.0.0/12")
            else:
                new_prefix = Prefix(
                    network="172.16.0.0",
                    prefix_length="12",
                    namespace=device_namespace,
                    location=device_location,
                    tenant=tenant_name,
                    status=status
                )
                new_prefix.save()
                self.logger.info(f"Created Prefix in Nautobot: 172.16.0.0/12")
                # Add IP address and associate with management interface
            
            existing_ip = IPAddress.objects.filter(host=firewall_ip, tenant=tenant_name)
            # Update ip
            if existing_ip:
                self.logger.info(f"IP already exists")
            else:
                new_ip = IPAddress(
                    host=firewall_ip,
                    mask_length="32",
                    namespace=device_namespace,
                    tenant=tenant_name,
                    dns_name=device_name,
                    status=status
                )
                new_ip.save()
                self.logger.info(f"Created ip in Nautobot: {device_ip}/32")

                
            #device_object = Device.objects.filter(serial=device_serial).first()
            device_ip_object = IPAddress.objects.filter(host=firewall_ip, tenant=tenant_name)
            existing_mgmt01 = Interface.objects.filter(device=device_object, name="mgmt01")
            
            if existing_mgmt01:
                self.logger.info(f"Interface mgmt01 already exists on {device_name} in Nautobot.")
            else:
                new_mgmt01 = Interface(
                    device=device_object,
                    name="mgmt01",
                    mgmt_only=True,
                    status=status,
                    type=InterfaceTypeChoices.TYPE_VIRTUAL
                )
                
                new_mgmt01.save()
                new_mgmt01.ip_addresses.set(device_ip_object)
                
                self.logger.info(f"Created interface mgmt01 on device {device_name} in Nautobot.")
            
            device_software = SoftwareVersion.objects.filter(version=device_software).first()
            primary_ip = IPAddress.objects.filter(host=firewall_ip, tenant=tenant_name).first()
            
            
            self.logger.info(f"Assigned IP {device_ip} to {device_name} management interface")


            obj_software = SoftwareVersion.objects.filter(name=f"{firewall_software}")
            # Update existing device
            existing_device.name = firewall_name
            existing_device.serial = firewall_serial
            existing_device.device_type = firewall_model
            existing_device.software_version = obj_software
            existing_device.custom_field_data["app_version"] = firewall_app
            existing_device.custom_field_data["anti_virus"] = firewall_av
            existing_device.custom_field_data["wildifre"] = firewall_wildfire
            existing_device.custom_field_data["url_filter"] = firewall_url_filter
            existing_device.custom_field_data["threat_version"]= firewall_threat
            existing_device.tenant = tenant_name
            existing_device.status = status
            existing_device.platform=firewall_platform
            existing_device.primary_ip4=primary_ip
            existing_device.role = Role.objects.filter(name="Firewall").first()
            existing_device.save()
            self.logger.info(f"Updated Device in Nautobot: {device_name}")


                
        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddorUpdatePanoramaandFirewall)