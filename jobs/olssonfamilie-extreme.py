import requests
from django.forms import ModelChoiceField
from nautobot.apps.jobs import Job, register_jobs
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceType, Interface, Location, LocationType, Manufacturer
from nautobot.tenancy.models import Tenant
from nautobot.ipam.models import IPAddress, Namespace
from nautobot.extras.models import Status, Role
from nautobot.extras.jobs import BooleanVar, ChoiceVar, FileVar, Job, ObjectVar, RunJobTaskFailed, StringVar, TextVar


class FetchAndAddExtremeCloudIQDevices(Job):
    class Meta:
        name = "Fetch and Add Devices from ExtremeCloud IQ"
        description = "Fetches devices from ExtremeCloud IQ and adds them to Nautobot."

    api_token = StringVar(
        description="API Token for ExtremeCloud IQ"
    )
    tenant_name = ObjectVar(
        model=Tenant,
        label="Tenant",
    )

    def run(self, api_token, tenant_name):
        tenant_name_string = str(tenant_name.name)
        base_url = 'https://api.extremecloudiq.com'
        headers = {
            'Authorization': f'Bearer {api_token}',
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
            manufacturer = Manufacturer.objects.filter(name="Extreme Networks").first()
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
                # Add IP address and associate with management interface
            if device_ip:
                ip_address, _ = IPAddress.objects.get_or_create(address=device_ip)
                management_interface, created = Interface.objects.get_or_create(
                    device=nautobot_device,
                    name='mgmt0',  # Adjust interface name as needed
                    defaults={'type': 'virtual'}  # Adjust interface type as needed
                )
                if not created:
                    self.logger.info(f"Management interface already exists for {device_name}")
                management_interface.ip_addresses.add(ip_address)
                management_interface.save()
                self.logger.info(f"Assigned IP {device_ip} to {device_name} management interface")


        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddExtremeCloudIQDevices)