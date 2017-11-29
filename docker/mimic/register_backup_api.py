#!/bin/python

from __future__ import print_function

import argparse
import json
import pprint
import sys
import uuid

import requests


class MimicManager(object):
    """
    """

    @staticmethod
    def make_template(ept_name, ept_id, ept_type, ept_region, ept_snet_url, ept_pubnet_url, ept_enabled):
        template = {
            'id': ept_id,
            'name': ept_name,
            'type': ept_type,
            'region': ept_region,
            'publicURL': ept_pubnet_url,
            'internalURL': ept_snet_url,
            'enabled': ept_enabled
        }
        if ept_snet_url is None:
            del template['internalURL']
        if ept_pubnet_url is None:
            del tempalte['publicURL']

        return template

    def __init__(self, mimic_server, mimic_server_port, mimic_ssl):
        self.server = '{0}:{1}'.format(
            mimic_server,
            mimic_server_port
        )
        protocol = 'http'
        if mimic_ssl:
            protocol = 'https'

        self.session = requests.Session()
        self.token = 'abc123'

        self.identity_url = '{0}://{1}/identity/v2.0'.format(
            protocol,
            self.server
        )
        self.tokens_url = '{0}/tokens'.format(
            self.identity_url
        )
        self.osksadm_url = '{0}/services'.format(
            self.identity_url
        )
        self.oskscatalog_url = '{0}/OS-KSCATALOG/endpointTemplates'.format(
            self.identity_url
        )
        print(
            'Identity URL: {0}\n'
            'Tokens URL: {1}\n'
            'OS-KSADM URL: {2}\n'
            'OS-KSCATALOG URL: {3}'.format(
                self.identity_url,
                self.tokens_url,
                self.osksadm_url,
                self.oskscatalog_url
            )
        )

    @property
    def headers(self):
        return {
            'X-Auth-Token': self.token
        }

    def get_service_catalog(self, on_console=True):
        """
        """
        data = {
            'auth': {
                'RAX-KSKEY:apiKeyCredentials': {
                    'username': 'mimic',
                    'apiKey': '12345'
                }
            }
        }
        response = self.session.post(
            self.tokens_url,
            data=json.dumps(data),
        )
        if response.status_code == 200:
            if on_console:
                print('Service Catalog:')
                pprint.pprint(response.json())
            else:
                return response.json()
        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )

    def get_service_from_service_catalog(self, service_type, on_console=True):
        """
        """
        service_catalog = self.get_service_catalog(on_console=False)
        if service_catalog is not None:
            for service in service_catalog['access']['serviceCatalog']:
                if service['type'] == service_type:
                    if on_console:
                        print(service)
                    else:
                        yield service


    def list_services(self, on_console=True):
        """
        """
        response = self.session.get(
            self.osksadm_url,
            headers=self.headers
        )
        if response.status_code == 200:
            body = response.json()
            if on_console:
                for service in body['OS-KSADM:services']:
                        print(
                            '\t{0}'.format(
                                service
                            )
                        )
            else:
                return body['OS-KSADM:services']

        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )

    def has_service(self, name, on_console=True):
        """
        """
        try:
            available = name in [
                service['name'] for service in
                self.list_services(on_console=False)
            ]

        except:
            available = False

        if on_console:
            print(
                'Is service {0} installed: {1}'.format(
                    name,
                    available
                )
            )

        else:
            return available
        

    def add_service(self, name, type_value):
        """
        """
        data = {
            'name': name,
            'type': type_value
        }
        response = self.session.post(
            self.osksadm_url,
            data=json.dumps(data).encode('utf-8'),
            headers=self.headers
        )
        if response.status_code == 201:
            print(
                'Created service.'
            )
        else:
            print(
                'Failed to create service: {0}'.format(
                    response.text
                )
            )


    def delete_service(self, serviceid, on_console=True):
        """
        """
        url = '{0}/{1}'.format(
            self.osksadm_url,
            serviceid
        )
        response = self.session.delete(
            url,
            headers=self.headers
        )
        if response.status_code == 204:
            print(
                'Deleted Service'
            )
        else:
            print(
                'Failed to delete service: {0}'.format(
                    response.text
                )
            )

    def list_templates(self, on_console=True):
        """
        """
        response = self.session.get(
            self.oskscatalog_url,
            headers=self.headers
        )
        if response.status_code == 200:
            body = response.json()
            if on_console:
                for ept in body['OS-KSCATALOG']:
                        print(
                            '\t{0}'.format(
                                ept
                            )
                        )
            else:
                return body['OS-KSCATALOG']

        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )

    def has_template(self, template_id, on_console=True):
        """
        """
        try:
            available = template_id in [
                ept['id'] for ept in
                self.list_templates(on_console=False)
            ]

        except:
            available = False

        if on_console:
            print(
                'Is template {0} installed: {1}'.format(
                    template_id,
                    available
                )
            )

        else:
            return available
        
    def add_template(self, template, service_id=None):
        """
        """
        headers = self.headers
        if service_id is not None:
            headers['serviceid'] = service_id

        response = self.session.post(
            self.oskscatalog_url,
            data=json.dumps(template),
            headers=self.headers
        )
        if response.status_code == 201:
            print(
                'Successfully added template'
            )
        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )

    def update_template(self, template, on_console=True, service_id=None):
        """
        """
        url = '{0}/{1}'.format(
            self.oskscatalog_url,
            template['id']
        )

        if service_id is not None:
            headers['serviceid'] = service_id

        response = self.session.put(
            url,
            data=json.dumps(template),
            headers=self.headers
        )
        if response.status_code == 201:
            print(
                'Successfully added template'
            )
        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )

    def delete_template(self, template_id, service_id=None):
        """
        """
        url = '{0}/{1}'.format(
            self.oskscatalog_url,
            template_id 
        )

        print(
            'Template Deletion URL: {0}'.format(
                url
            )
        )

        headers = self.headers

        if service_id is not None:
            headers['serviceid'] = service_id

        response = self.session.delete(
            url,
            headers=self.headers
        )
        if response.status_code == 204:
            print(
                'Successfully added template'
            )
        else:
            print(
                'Error: {0}'.format(
                    response.text
                )
            )


def list_services(arguments, manager):
    print('Listing Services:')
    manager.list_services()
    return 0

def add_service(arguments, manager):
    print(
        'Attempting to add Service {0} with type {1}'.format(
            arguments.name,
            arguments.type
        )
    )
    manager.add_service(arguments.name, arguments.type)
    return 0

def remove_service(arguments, manager):
    print(
        'Attempting to remove service with id {0}'.format(
            arguments.service_id
        )
    )
    manager.delete_service(arguments.service_id)
    return 0

def list_templates(arguments, manager):
    print('Listing Templates:')
    manager.list_templates()
    return 0

def add_template(arguments, manager):
    print('Attempting to add Template')
    template = MimicManager.make_template(
        arguments.name,
        arguments.template_id,
        arguments.type,
        arguments.region,
        arguments.public_url,
        arguments.internal_url,
        arguments.enabled
    )
    manager.add_template(template)

def remove_template(arguments, manager):
    print('Removing Template')
    mm.delete_template(
        arguments.template_id,
        arguuments.service_id
    )

def update_template(arguments, manager):
    print('Updating Template')
    template = MimicManager.make_template(
        arguments.name,
        arguments.template_id,
        arguments.type,
        arguments.region,
        arguments.public_url,
        arguments.internal_url,
        arguments.enabled
    )
    manager.update_template(
        template
    )


def test_for_service(arguments, manager):
    print('Checking for ' + arguments.type + ' in Service Catalog:')
    for service in manager.get_service_from_service_catalog(arguments.type):
        print(
            '\t{0}'.format(
                service
            )
        )


def main():
    def parser_add_serviceid(parser, required=False, default_value=None):
        parser.add_argument('-s', '--service-id', type=str, required=required, default=default_value, help='Service UUID')

    def parser_add_service_name(parser, required=False, default_value='Cloud Backup'):
        parser.add_argument('-n', '--name', type=str, required=required, default=default_value, help='Service Name')

    def parser_add_service_type(parser, required=False, default_value='rax:backup'):
        parser.add_argument('-t', '--type', type=str, required=required, default=default_value, help='Service Type')

    def parser_add_region(parser, required=False, default_value='ORD'):
        parser.add_argument('-r', '--region', type=str, required=False, default=default_value, help='Region for Endpoint Template')

    def parser_add_publicurl(parser, required=True):
        parser.add_argument('-p', '--public-url', type=str, required=True, help='Public URL for Endpoint Template')

    def parser_add_internalurl(parser, required=True):
        parser.add_argument('-i', '--internal-url', type=str, required=True, help='Public URL for Endpoint Template')

    def parser_add_templateid(parser, required=False, default_value=uuid.uuid4()):
        parser.add_argument('-tid', '--template-id', type=str, required=required, default=default_value, help='Template ID')

    def parser_add_enable_template(parser):
        parser.add_argument('-e', '--enabled', default=False, action='store_true', help='Enable Template')

    argument_parser = argparse.ArgumentParser(description='Mimic Manager')
    argument_parser.add_argument('--mimic-server', default='localhost', type=str, required=False, help='Server Name or IP for Mimic, e.g localhost')
    argument_parser.add_argument('--mimic-server-port', default='8900', type=int, required=False, help='Port on which the Mimic Server is running')
    argument_parser.add_argument('--mimic-uses-ssl', default=False, action='store_true', help='Use HTTPS instead of HTTP')
    sub_arg_parser = argument_parser.add_subparsers(title='commands')

    service_parser = sub_arg_parser.add_parser('services', help='Manage Services in Service Catalog')
    service_sub_parser = service_parser.add_subparsers(title='command')

    list_service_parser = service_sub_parser.add_parser('list', help='List Services')
    list_service_parser.set_defaults(func=list_services)

    add_service_parser = service_sub_parser.add_parser('add', help='Add Service')
    parser_add_service_name(add_service_parser)
    parser_add_service_type(add_service_parser)
    add_service_parser.set_defaults(func=add_service)

    remove_service_parser = service_sub_parser.add_parser('remove', help='Remove Service')
    parser_add_serviceid(remove_service_parser, required=True)
    remove_service_parser.set_defaults(func=remove_service)


    check_service_parser = service_sub_parser.add_parser('check', help='Check for service in Service Catalog')
    parser_add_service_type(check_service_parser)
    check_service_parser.set_defaults(func=test_for_service)

    template_parser = sub_arg_parser.add_parser('templates', help='Manage Templates for Services')
    template_sub_parser = template_parser.add_subparsers(title='command')

    list_template_parser = template_sub_parser.add_parser('list', help='List Templates')
    list_template_parser.set_defaults(func=list_templates)

    add_template_parser = template_sub_parser.add_parser('add', help='Add Template')
    #parser_add_serviceid(add_template_parser)
    parser_add_service_name(add_template_parser, required=True)
    parser_add_service_type(add_template_parser, required=True)
    parser_add_region(add_template_parser)
    parser_add_templateid(add_template_parser, required=True)
    parser_add_publicurl(add_template_parser)
    parser_add_internalurl(add_template_parser)
    parser_add_enable_template(add_template_parser)
    add_template_parser.set_defaults(func=add_template)

    remove_template_parser = template_sub_parser.add_parser('remove', help='Remove Template')
    parser_add_serviceid(remove_template_parser)
    parser_add_templateid(remove_template_parser, required=True)
    remove_template_parser.set_defaults(func=remove_template)

    update_template_parser = template_sub_parser.add_parser('update', help='Update Template')
    #parser_add_serviceid(update_template_parser)
    parser_add_service_name(update_template_parser)
    parser_add_service_type(update_template_parser)
    parser_add_region(update_template_parser)
    parser_add_templateid(update_template_parser, required=True)
    parser_add_publicurl(update_template_parser)
    parser_add_internalurl(update_template_parser)
    parser_add_enable_template(update_template_parser)
    update_template_parser.set_defaults(func=update_template)

    arguments = argument_parser.parse_args()

    manager = MimicManager(
        arguments.mimic_server,
        arguments.mimic_server_port,
        arguments.mimic_uses_ssl
    )

    return arguments.func(arguments, manager)


def test_1():
    backup_template = MimicManager.make_template(
        'Cloud Backup',
        str(uuid.uuid4()),
        'rax:backup',
        'ORD',
        'http://104.239.138.38/v1.0/',
        'http://104.239.138.38/v1.0/',
        False
    )

    mm = MimicManager('localhost', 8900, False)

    def ls_services():
        print('Listing Services:')
        mm.list_services()
        mm.has_service('Cloud Backup')

    def ls_templates():
        print('Listing Templates:')
        mm.list_templates()
        mm.has_template(backup_template['id'])

    def get_cloudbackup_service_id():
        for service in mm.list_services(on_console=False):
            if service['name'] == 'Cloud Backup':
                return service['id']

    def check_service_catalog():
        print('Service Catalog:')
        for service in mm.get_service_from_service_catalog('rax:backup'):
            print(
                '\t{0}'.format(
                    service
                )
            )

    ls_services()
    check_service_catalog()
    mm.add_service('Cloud Backup', 'rax:backup')
    ls_services()
    check_service_catalog()

    mm.add_service('Cloud Backup', 'rax:backup')

    ls_templates()
    mm.add_template(backup_template)

    ls_templates()
    check_service_catalog()

    backup_template['enabled'] = True
    mm.update_template(backup_template)

    ls_templates()
    check_service_catalog()

    backup_service_id = get_cloudbackup_service_id()
    templates = mm.list_templates(on_console=False)
    for template in templates:
        mm.delete_template(
            template['id'],
            service_id=backup_service_id
        )

    ls_templates()
    check_service_catalog()

    # cleanup
    services = mm.list_services(on_console=False)
    for service in services:
        mm.delete_service(service['id'])

    ls_services()
    check_service_catalog()

if __name__ == "__main__":
    sys.exit(main())
