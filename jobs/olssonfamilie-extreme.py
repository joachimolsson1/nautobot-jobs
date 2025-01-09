import requests
from django.forms import ModelChoiceField
from nautobot.apps.jobs import Job, register_jobs
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceType, Interface, Location, LocationType, Platform, SoftwareVersion
from nautobot.dcim.choices import InterfaceTypeChoices
from nautobot.tenancy.models import Tenant
from nautobot.ipam.models import IPAddress, Namespace, Prefix
from nautobot.extras.models import Status, Role
from nautobot.extras.secrets import get_secret_value
from nautobot.extras.jobs import BooleanVar, ChoiceVar, FileVar, Job, ObjectVar, RunJobTaskFailed, StringVar, TextVar


class FetchAndAddExtremeCloudIQDevices(Job):
    class Meta:
        name = "Fetch and Add Devices from ExtremeCloud IQ"
        description = "Fetches devices from ExtremeCloud IQ and adds them to Nautobot."

    #api_token = StringVar(
    #    description="API Token for ExtremeCloud IQ"
    #)
    #tenant_name = ObjectVar(
    #    model=Tenant,
    #    label="Tenant",
    #)

    def run(self, tenant_name):
        secret_apikey = get_secret_value("extremeapi.olssonfamilie")
        tenants = Tenant.objects.filter(custom_field_data__contains={"Services": "Network as a Service"})
        
        for tenant_name in tenants:
            tenant_name_string = str(tenant_name.name)
            base_url = 'https://api.extremecloudiq.com'
            headers = {
                'Authorization': f'Bearer {secret_apikey}',
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
                #tenant = Tenant.objects.get(name=f"{tenant_name}")
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
                #manufacturer = Manufacturer.objects.filter(name="Extreme Networks").first()
                if existing_device:
                    # Update existing device
                    existing_device.name = device_name
                    existing_device.role = role_existing
                    existing_device.device_type = device_type
                    #existing_device.site = site
                    existing_device.status = status
                    #existing_device.manufacturer = "Extreme Networks"
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
                        #manufacturer=manufacturer,
                        device_type=device_type,
                        tenant=tenant_name,
                        #site=site,
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
                        #ip_addresses=device_ip_object,
                        status=status,
                        type=InterfaceTypeChoices.TYPE_VIRTUAL
                    )
                    
                    new_mgmt01.save()
                    new_mgmt01.ip_addresses.set(device_ip_object)

                    #mgmt01_object = Interface.objects.filter(device=device_object, name="mgmt0")
                    #device_ip_object.assigned_object = mgmt01_object
                    #mgmt01_object.ip_addresses.add(device_ip_object)
                    #mgmt01_object.save()
                    #mgmt01_interface = Interface.objects.filter(device=device_object, name="mgmt0")
                    
                    self.logger.info(f"Created interface mgmt01 on device {device_name} in Nautobot.")

                # Software
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
                
                device_software = SoftwareVersion.objects.filter(version=device_software).first()
                primary_ip = IPAddress.objects.filter(host=device_ip, tenant=tenant_name).first()
                update_device = Device.objects.filter(serial=device_serial).first()
                update_device.primary_ip4=primary_ip
                update_device.name = device_name
                update_device.role = role_existing
                update_device.device_type = device_type
                update_device.platform=device_platform
                update_device.software_version=device_software
                #existing_device.site = site
                update_device.status = status
                #existing_device.manufacturer = "Extreme Networks"
                update_device.location = device_location  # Set the last location as campus
                update_device.tenant = tenant_name
                update_device.save()
                self.logger.info(f"Assigned IP {device_ip} to {device_name} management interface")


        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddExtremeCloudIQDevices)