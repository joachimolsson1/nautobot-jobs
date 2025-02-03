import requests
import json
import xmltodict
import base64
from datetime import datetime

from nautobot.apps.jobs import Job, register_jobs
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceType, Interface, Location, LocationType, Platform, SoftwareVersion
from nautobot.dcim.choices import InterfaceTypeChoices
from nautobot.tenancy.models import Tenant
from nautobot.ipam.models import IPAddress, Namespace, Prefix
from nautobot.extras.models import Status, Role, Secret, CustomField
from django.contrib.contenttypes.models import ContentType
from nautobot.extras.choices import CustomFieldTypeChoices
from nautobot.extras.jobs import Job


class FetchAndAddorUpdatePanoramaandFirewall(Job):
    class Meta:
        name = "Fetch, Add and Update Panorama and Firewall objects"
        description = "Fetches devices from Panorama and Firewalls from Nautobot devices tagged with Firewall as a Service updates the objects in Nautobot."

    def run(self):
        #Panorama
        device_role = Role.objects.filter(name="Panorama")
        devices = Device.objects.filter(_custom_field_data__icontains='Firewall as a Service')
        self.logger.info(f"{devices}")
        for device in devices:
            if device.role == device_role:

                device_name_string = str(device.name)
                #self.logger.info(tenant_name_string)
                command = ""
                auth_username = Secret.username
                auth_password = Secret.password
                encoded_auth = base64.b64encode(data.encode("utf-8"))
                secret_apikey = Secret.objects.get(name=f"{device_name_string} Panorama").get_values()
                base_url = f'https://{host}/api/?type=op&cmd=${command}'
                headers = {
                    'Authorization': f'Basic {secret_apikey}',
                    'Content-Type': 'application/json'
                }
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

                else:
                    break


 

        #Firewall
        device_role = Role.objects.filter(name="Firewall")
        devices_firewall = Device.objects.filter(_custom_field_data__icontains='Firewall as a Service')
        for device_firewall in devices_firewall:
            if device_firewall.role == device_role:
            
                device_name_string = str(device_firewall.name)
                #device_loopback_url = device_firewall.custom_field_data["loopback_url"]
                tenant_name = device_firewall.tenant
                tenant_name_string = str(device_firewall.tenant)
                command =  "<show><system><info></info></system></show>"
                secret_apikey = Secret.objects.get(name=f"{device_name_string} Firewall").get_values()
                #auth_encode = f"{Secret.username}:{Secret.password}"
                #encoded_auth = base64.b64encode(auth_encode.encode("utf-8"))

                headers = {
                    'Authorization': f'Basic {secret_apikey}'
                }
                # System Info
                response_xml = requests.get(f'https://10.10.50.1:4443/api/?type=op&cmd=${command}',headers=headers)
                    
                if response_xml.status_code != 200:
                    self.logger.error(f"Error: {response.status_code}")
                    break
                
                dict_data = xmltodict.parse(response_xml)
                devices_firewall = json.dumps(dict_data, indent=4)
                firewall_device = json.loads(device_firewall)

                firewall_name = firewall_device.get('hostname')
                firewall_serial = firewall_device.get('serial')
                firewall_model = firewall_device.get('model')
                firewall_ip = firewall_device.get('ip-address')
                firewall_software = firewall_device.get('sw-version')
                firewall_app = firewall_device.get('app-version')
                firewall_av = firewall_device.get('av-version')
                firewall_wildfire = firewall_device.get('wildfire-version')
                firewall_url_filter = firewall_device.get('url-filtering-version')
                firewall_threat = firewall_device.get('threat-version')
                
                firewall_platform= Platform.objects.filter(name="PAN OS").first()
                existing_software=SoftwareVersion.objects.filter(version=device_software).first()
                # Create Software
                if existing_software:
                    self.logger.info(f"Software {device_software} already exists.")

                else:
                    new_software = SoftwareVersion(
                        version=firewall_software,
                        platform=firewall_platform,
                        status=status
                    )
                    new_software.save()
                    self.logger.info(f"Software {device_software} was created in Nautobot.")
                
                #Device variables
                existing_firewall_device = Device.objects.filter(id=device_firewall.id).first()
                obj_software = SoftwareVersion.objects.filter(name=f"{firewall_software}")

                ## License
                command_license =  "<request><license><info></info></license></request>"

                response_licese = requests.get(f'https://10.10.50.1:4443/api/?type=op&cmd={command_license}',headers=headers, verify=False)
                if response_licese.status_code != 200:
                    print(response.text)
                    
                xml_data = response.content
                dict_data = xmltodict.parse(xml_data)
                device_license = json.dumps(dict_data)
                device_license_json = json.loads(device_license)
                for license in device_license_json["response"]["result"]["licenses"]["entry"]:
                    custom_field_exists = CustomField.objects.filter(label=f"{license["feature"]}").exists()
                    date = license["expires"]
                    if date == "Never":
                        break
                    else:
                        if custom_field_exists:
                            date_obj = datetime.strptime(date, "%B %d, %Y")
                            iso_date = date_obj.isoformat()
                            existing_firewall_device.custom_field_data[f"{license["feature"]}"] = iso_date
                            existing_firewall_device.save()
                        else:
                            custom_field = CustomField(
                                name=license["feature"],
                                type=CustomFieldTypeChoices.TYPE_DATE,
                                required=False,
                                description=""
                            )
                            custom_field.save()
                            # Apply the custom field to the Device model
                            device_content_type = ContentType.objects.get_for_model(Device)
                            custom_field.content_types.add(device_content_type)
                            date_obj = datetime.strptime(date, "%B %d, %Y")
                            iso_date = date_obj.isoformat()
                            existing_firewall_device.custom_field_data[f"{license["feature"]}"] = iso_date
                            existing_firewall_device.save()




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


                
                # Update existing device
                existing_firewall_device.name = firewall_name
                existing_firewall_device.serial = firewall_serial
                existing_firewall_device.device_type = firewall_model
                existing_firewall_device.software_version = obj_software
                existing_firewall_device.custom_field_data["app_version"] = firewall_app
                existing_firewall_device.custom_field_data["anti_virus"] = firewall_av
                existing_firewall_device.custom_field_data["wildifre"] = firewall_wildfire
                existing_firewall_device.custom_field_data["url_filter"] = firewall_url_filter
                existing_firewall_device.custom_field_data["threat_version"]= firewall_threat
                existing_firewall_device.tenant = tenant_name
                existing_firewall_device.status = status
                existing_firewall_device.platform=firewall_platform
                existing_firewall_device.primary_ip4=primary_ip
                existing_firewall_device.role = Role.objects.filter(name="Firewall").first()
                existing_firewall_device.save()
                self.logger.info(f"Updated Device in Nautobot: {device_name}")
            else:
                break


                
        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddorUpdatePanoramaandFirewall)