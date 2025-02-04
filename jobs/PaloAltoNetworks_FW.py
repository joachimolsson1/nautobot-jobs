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
        name = "Update Firewall objects"
        description = "Firewalls from Nautobot devices tagged with Firewall as a Service updates the objects in Nautobot."

    def run(self):
        #Firewall
        device_role = Role.objects.filter(name="Firewall")
        devices_firewall = Device.objects.filter(_custom_field_data__icontains='Firewall as a Service')
        for device_firewall in devices_firewall:
            if str(device_firewall.role) == "Firewall":
            
                device_name_string = str(device_firewall.name)
                #device_loopback_url = device_firewall.custom_field_data["loopback_url"]
                tenant_name = device_firewall.tenant
                tenant_name_string = str(device_firewall.tenant)
                command =  "<show><system><info></info></system></show>"
                self.logger.info(device_name_string)
                secret_apikey = Secret.objects.get(name=f"{device_name_string} Firewall").get_value()
                #auth_encode = f"{Secret.username}:{Secret.password}"
                #encoded_auth = base64.b64encode(auth_encode.encode("utf-8"))

                headers = {
                    'Authorization': f'Basic {secret_apikey}'
                }
                # System Info
                response_xml = requests.get(f'https://10.10.50.1:4443/api/?type=op&cmd={command}',headers=headers, verify=False)
                    
                if response_xml.status_code != 200:
                    self.logger.error(f"Error: {response.status_code}")
                    break
                self.logger.info(response_xml.status_code)
                self.logger.info(response_xml.text)
                xml_data = response_xml.content
                dict_data = xmltodict.parse(xml_data)
                devices_firewall = json.dumps(dict_data)
                firewall_device = json.loads(devices_firewall)

                firewall_name = firewall_device["response"]["result"]["system"]["hostname"]
                firewall_serial = firewall_device["response"]["result"]["system"]["serial"]
                firewall_model = firewall_device["response"]["result"]["system"]["model"]
                firewall_ip = firewall_device["response"]["result"]["system"]["ip-address"]
                firewall_software = firewall_device["response"]["result"]["system"]["sw-version"]
                firewall_app = firewall_device["response"]["result"]["system"]["app-version"]
                firewall_av = firewall_device["response"]["result"]["system"]["av-version"]
                firewall_wildfire = firewall_device["response"]["result"]["system"]["wildfire-version"]
                firewall_url_filter = firewall_device["response"]["result"]["system"]["url-filtering-version"]
                firewall_threat = firewall_device["response"]["result"]["system"]["threat-version"]
                
                firewall_platform= Platform.objects.filter(name="PAN OS").first()
                existing_software=SoftwareVersion.objects.filter(version=firewall_software).first()
                # Create Software
                self.logger.info(firewall_software)
                if existing_software:
                    self.logger.info(f"Software {firewall_software} already exists.")

                else:
                    new_software = SoftwareVersion(
                        version=firewall_software,
                        platform=firewall_platform,
                        status=status
                    )
                    new_software.save()
                    self.logger.info(f"Software {firewall_software} was created in Nautobot.")
                
                #Device variables
                existing_firewall_device = Device.objects.filter(id=device_firewall.id).first()
                obj_software = SoftwareVersion.objects.filter(version=f"{firewall_software}").first()
                obj_device_type = DeviceType.objects.get(model=firewall_model)

                ## License
                command_license =  "<request><license><info></info></license></request>"

                response_license = requests.get(f'https://10.10.50.1:4443/api/?type=op&cmd={command_license}',headers=headers, verify=False)
                if response_license.status_code != 200:
                    print(response.text)
                    
                xml_data = response_license.content
                dict_data = xmltodict.parse(xml_data)
                device_license = json.dumps(dict_data)
                device_license_json = json.loads(device_license)
                for license in device_license_json["response"]["result"]["licenses"]["entry"]:
                    custom_field_exists = CustomField.objects.filter(label=f"License: {license["feature"]}").exists()
                    date = license["expires"]
                    if date == "Never":
                        break
                    else:
                        if custom_field_exists:
                            date_obj = datetime.strptime(date, "%B %d, %Y").date()
                            iso_date = date_obj.isoformat()
                            # Step 2: Convert to lowercase
                            parsed_string = license["feature"].lower()
                            # Step 3: Replace spaces with underscores
                            parsed_string = parsed_string.replace(" ", "_")
                            parsed_string = parsed_string.replace("-", "_")
                            # Add the prefix "license_"
                            final_string = "license_" + parsed_string
                            self.logger.info(final_string)
                            existing_firewall_device.custom_field_data[f"{final_string}"] = iso_date
                            existing_firewall_device.save()
                            self.logger.info(f"Added date {iso_date} to license {license["feature"]}")
                        else:
                            custom_field = CustomField(
                                label=f"License: {license["feature"]}",
                                grouping="Palo Alto Licenses:",
                                type=CustomFieldTypeChoices.TYPE_DATE,
                                required=False,
                                description=""
                            )
                            custom_field.save()
                            # Apply the custom field to the Device model
                            device_content_type = ContentType.objects.get_for_model(Device)
                            custom_field.content_types.add(device_content_type)
                            date_obj = datetime.strptime(date, "%B %d, %Y").date()
                            iso_date = date_obj.isoformat()
                            parsed_string = license["feature"].lower()
                            # Step 3: Replace spaces with underscores
                            parsed_string = parsed_string.replace(" ", "_")
                            parsed_string = parsed_string.replace("-", "_")
                            # Add the prefix "license_"
                            final_string = "license_" + parsed_string
                            self.logger.info(final_string)
                            existing_firewall_device.custom_field_data[f"{final_string}"] = iso_date
                            existing_firewall_device.save()
                            self.logger.info(f"Created and Added date {iso_date} to license {license["feature"]}")




                # Namespace
                # Update Namespace
                firewall_location = device_firewall.location
                existing_namespace = Namespace.objects.filter(name=tenant_name).first()
                if existing_namespace:
                    existing_namespace.name = tenant_name_string
                    existing_namespace.location = firewall_location
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
                    existing_prefix.location = firewall_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 10.0.0.0/8")
                else:
                    new_prefix = Prefix(
                        network="10.0.0.0",
                        prefix_length="8",
                        namespace=device_namespace,
                        location=firewall_location,
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
                    existing_prefix.location = firewall_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 192.168.0.0/16")
                else:
                    new_prefix = Prefix(
                        network="192.168.0.0",
                        prefix_length="16",
                        namespace=device_namespace,
                        location=firewall_location,
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
                    existing_prefix.location = firewall_location
                    existing_prefix.tenant = tenant_name
                    existing_prefix.status = status
                    existing_prefix.save()
                    self.logger.info(f"Updated Prefix in Nautobot: 172.16.0.0/12")
                else:
                    new_prefix = Prefix(
                        network="172.16.0.0",
                        prefix_length="12",
                        namespace=device_namespace,
                        location=firewall_location,
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
                        dns_name=device_name_string,
                        status=status
                    )
                    new_ip.save()
                    self.logger.info(f"Created ip in Nautobot: {firewall_ip}/32")

                    
                #device_object = Device.objects.filter(id=device_serial).first()
                device_ip_object = IPAddress.objects.filter(host=firewall_ip, tenant=tenant_name)
                existing_mgmt01 = Interface.objects.filter(device=device_firewall, name="mgmt01")
                
                if existing_mgmt01:
                    self.logger.info(f"Interface mgmt01 already exists on {firewall_name} in Nautobot.")
                else:
                    new_mgmt01 = Interface(
                        device=device_firewall,
                        name="mgmt01",
                        mgmt_only=True,
                        status=status,
                        type=InterfaceTypeChoices.TYPE_VIRTUAL
                    )
                    
                    new_mgmt01.save()
                    new_mgmt01.ip_addresses.set(device_ip_object)
                    
                    self.logger.info(f"Created interface mgmt01 on device {firewall_name} in Nautobot.")
                
                primary_ip = IPAddress.objects.filter(host=firewall_ip, tenant=tenant_name).first()
                
                
                self.logger.info(f"Assigned IP {firewall_ip} to {firewall_name} management interface")


                
                # Update existing device
                existing_firewall_device.name = firewall_name
                existing_firewall_device.serial = firewall_serial
                existing_firewall_device.device_type = obj_device_type
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
                self.logger.info(f"Updated Device in Nautobot: {firewall_name}")
            else:
                break


                
        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddorUpdatePanoramaandFirewall)