import requests
from django.forms import ModelChoiceField
from nautobot.apps.jobs import Job, register_jobs
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceType, Interface, Location, Manufacturer
from nautobot.tenancy.models import Tenant
from nautobot.ipam.models import IPAddress
from nautobot.extras.models import Status
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
        #api_token = data["api_token"]
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

            # Fetch or create the necessary related objects
            device_type, _ = DeviceType.objects.get_or_create(model=device_model)
            status = Status.objects.get(name='Active')  # Adjust status as needed

            tenant = Tenant.objects.get(name=f"{tenant_name}")
            # Create or fetch location 
            location = Location.objects.get_or_create(
                name=device["locations"][1],
                tenant=tenant
            )


            # Check for existing device
            existing_device = Device.objects.filter(serial=device_serial).first()
            if existing_device:
                # Update existing device
                existing_device.name = device_name
                #existing_device.device_role = device_role
                existing_device.device_type = device_type
                #existing_device.site = site
                existing_device.status = status
                existing_device.manufacturer = "Extreme Networks"
                existing_device.location = location  # Set the last location as campus
                existing_device.tenant = tenant
                existing_device.save()
                self.logger.info(f"Updated Device in Nautobot: {device_name}")
            else:
                # Create new device
                nautobot_device = Device(
                    name=device_name,
                    serial=device_serial,
                    #device_role=device_role,
                    manufacturer="Extreme Networks",
                    device_type=device_type,
                    tenant=tenant,
                    #site=site,
                    status=status,
                    location=location  # Set the last location as campus
                )
                nautobot_device.save()
                self.logger.info(f"Added Device to Nautobot: {device_name}")

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