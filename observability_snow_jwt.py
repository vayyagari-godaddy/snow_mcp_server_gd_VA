#!/usr/bin/python
# coding: utf-8
from datetime import datetime
import json
import requests
from base64 import b64encode
import logging
import os
logger = logging.getLogger(__name__)
import webbrowser
import urllib.parse
import binascii
from pydantic import BaseModel, Field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pydantic_core.core_schema import arguments_schema
from dotenv import load_dotenv
load_dotenv()
try:
    from gd_servicenow_api.incident_state import IncidentState
    from gd_servicenow_api.data_processor import DataProcessor
    from gd_servicenow_api.data_processor_environment import DataProcessorEnvironment
    from gd_servicenow_api.public_cloud_account import PublicCloudAccount
    from gd_servicenow_api.table import Table
    from gd_servicenow_api.ci_relationship_type import CIRelationshipType
    from gd_servicenow_api.ci_relationship import CIRelationship
    from gd_servicenow_api.database import Database
except ModuleNotFoundError:
    from gd_servicenow_api.incident_state import IncidentState
    from gd_servicenow_api.data_processor import DataProcessor
    from gd_servicenow_api.data_processor_environment import DataProcessorEnvironment
    from gd_servicenow_api.public_cloud_account import PublicCloudAccount
    from gd_servicenow_api.table import Table
    from gd_servicenow_api.ci_relationship_type import CIRelationshipType
    from gd_servicenow_api.ci_relationship import CIRelationship
    from gd_servicenow_api.database import Database
try:
    from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError, MissingParameterError, DataProcessorAlreadyExists)
except ModuleNotFoundError:
    from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError, MissingParameterError, DataProcessorAlreadyExists)
except ImportError:
    from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError, MissingParameterError,
                            DataProcessorAlreadyExists)


read_relationship_type_name = "Read by::Reads from"
write_relationship_type_name = "Writes to::Written by"
code = ''
state = binascii.hexlify(os.urandom(20)).decode('utf-8')

class ObservabilityServiceNow:

    def __init__(
        self, username = None, password = None, client_id = None, client_secret = None, servicenow_api_url = None
    ) -> None:

        self._session = requests
        self.url = servicenow_api_url
        self.headers_api = None
        self.client_id = os.getenv('JWT_CLIENT_ID')
        self.client_secret = os.getenv('JWT_CLIENT_SECRET')
        self.server, self.port = 'localhost', 8080
        self._redirect_uri = f'http://{self.server}:{self.port}'
        self._last_request_time = 0
        self.auth_url=os.getenv('JWT_AUTH_URL')
        self.token_url=os.getenv('JWT_TOKEN_URL')

        user_pass = f'{client_id}:{client_secret}'.encode()
        user_pass_encoded = b64encode(user_pass).decode()

        self.known_assignment_groups = dict()
        self.known_ci_cmdb = dict()
        self.known_ci_cmdb_status = dict()
        self.auth()

    def auth(self):
        # scope = ' '.join(args)

        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self._redirect_uri,
            # 'scope': 'openid',
            'state': state
        }
        request = requests.Request('GET', self.auth_url, params).prepare()
        request.prepare_url(self.auth_url, params)
        webbrowser.open(request.url)

        server = HTTPServer((self.server, self.port), RequestHandler)
        server.handle_request()
        # print(f'Server response: {code}')
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self._redirect_uri
        }
        self._get_token(payload)
        # print(self.token)


    def _get_token(self, payload):
        r = requests.post(self.token_url, data=payload)
        if r.status_code == 403:
            raise UnauthorizedError
        elif r.status_code == 401:
            raise AuthError
        elif r.status_code == 404:
            raise ParameterError

        data = json.loads(r.text)
        # print( data['id_token'])
        self.id_token = data['id_token']
        self.token = data['access_token']
        self.refresh_token = data['refresh_token']
        self.headers_api = {
            'accept': 'application/json',
            'Authorization': 'Bearer ' + self.id_token,
        }


    def get_table(
        self, table: str, sys_id: str = None, name: str = None, rows: int = 1, name_override: str = None, offset: int =0, extra_params: str = None
    ):
        """Returns the table and a response code. Response code 200 is success, everything else is a failure"""

        query_path = table
        if sys_id:
            query_path = f"{query_path}/{sys_id}"
        name_encoded = quote_plus(name) if name else None
        key = name_override if name_override else 'name'
        url = f'{self.url}/api/now/table/{query_path}?sysparm_limit={rows}&sysparm_offset={offset}'
        if name:
            url = f'{url}&{key}={name_encoded}'
        if extra_params:
            url = f'{url}&{extra_params}'
        response = self._session.get(url, headers=self.headers_api)
        try:
            return response.json(), response.headers, response.status_code
        except (ValueError, AttributeError):
            return response, response.headers, response.status_code
        
    def get_table_with_offset(
            self, table: str, sys_id: str = None, name: str = None, rows: int = 10000, name_override: str = None, offset: int =0, extra_params: str = None
    ):
        block_size = rows
        results = list()
        rows_returned = block_size
        offset = 0
        while (rows_returned):
            response, table_headers, response_code = self.get_table(table=table, sys_id=sys_id, name=name, rows=block_size, name_override=name_override, offset=offset, extra_params=extra_params)
            if 'rel="next"' in table_headers.get('Link', ""):
                rows_returned = len(response["result"])
                results.extend(response["result"])
                offset += rows_returned
            else:
                results.extend(response["result"])
                break

        return dict({'result': results}), response_code

    def download_table_as_csv(self, filename:str, table_name: str, max_rows: int = None):
        """Downloads the table into a file"""

        block_size = 1000
        if max_rows:
            if block_size > max_rows:
                block_size = max_rows

        results = list()
        rows_returned = block_size
        offset = 0
        while (rows_returned):
            print(f"Getting {block_size} rows, now offset {offset}")
            table, table_headers, response_code = self.get_table(table=table_name,rows=block_size, offset=offset)
            if response_code!=200 or table.get("result") is None:
                print(json.dumps(table))
                break
            rows_returned = len(table["result"])
            results.extend(table["result"])
            #offset += rows_returned
            offset += block_size
            print(f"return {rows_returned}, now offset {offset}")
            if max_rows:
                if offset>= max_rows:
                    break
        print(f"Writing to {filename}")
        f = open(filename, "w")
        f.write(json.dumps(results))
        f.close


    def load_assignment_group(self, name: str) -> object:
        table, response_code = self.get_table_with_offset(table="sys_user_group", name=name)
        if response_code != 200:
            return None
        row = table.get("result")[0] if table.get("result") else {}
        if "name" in row:
            self.known_assignment_groups[row["name"]] = row
        return row

    def load_cmdb_ci(self, name: str):
        table, response_code = self.get_table_with_offset(table="cmdb_ci", name=name)
        if response_code != 200:
            return None
        row = table.get("result", [{}])[0]
        if "name" in row:
            self.known_ci_cmdb[row["name"]] = row
        return row
        
    def get_cmdb_ci_db_datalake(self, name: str):
        table, response_code = self.get_table_with_offset(table="u_cmdb_ci_aws_data_lake", name=name)
        if response_code != 200:
            return None
        row = table.get("result", [{}])[0]
        return row
        
    def get_cmdb_ci_table(self, ci: dict):
        name = ci.get("name")
        table, response_code = self.get_table_with_offset(table="u_cmdb_ci_database_table_instance", name=name)
        if response_code != 200:
            return None 
        
        db_name = ci.get("database")
        db, response_code = self.get_table_with_offset(table=ci.get("db_class"), name=db_name)
        if response_code != 200:
            return None
        
        for table_row in table["result"]:
            for db_row in db["result"]:
                table_u_database_instance = table_row.get("u_database_instance", {}).get("value")
                if db_row.get("sys_id") == table_u_database_instance:
                    return table_row

    def load_cmdb_ci_status(self, name: str):
        table, response_code = self.get_table_with_offset(table="u_cmdb_ci_status", name=name)
        if response_code != 200:
            return None
        row = table.get("result", [{}])[0]
        if "name" in row:
            self.known_ci_cmdb_status[row["name"]] = row
        return row

    def get_cmdb_ci(self, sys_id: str = None, name: str = None):
        """Returns the CMDI CI Item and response code. Response code 200 is a success, everything else is a failure"""

        return self.get_table_with_offset(table="cmdb_ci", name=name, sys_id=sys_id)
    
    def get_ci(self, cmdb_ci: dict):
        ci_class = cmdb_ci.get("ci_class")
        if ci_class == "u_cmdb_ci_database_table_instance":
            ci_table = self.get_cmdb_ci_table(cmdb_ci)
            return ci_table
        
    def get_incident_dna_info(self, number: str):
        response = self._session.get(f'{self.url}/api/gmi/variable_updater/{number}', headers=self.headers_api)
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code


    def create_incident(
        self, incident: dict, assignment_group_name: str, cmdb_ci: dict = None, default_assignment_group: str = 'DnA_Ops_Support_Group'
    ):
        """Returns the Incident created response code. Response code 201 is a success, everything else is a failure"""

        if assignment_group_name:
            val = self.known_assignment_groups.get(assignment_group_name) or self.load_assignment_group(assignment_group_name)
            if val:
                incident["assignment_group"] = val.get("sys_id", None)
                incident["description"] += assignment_group_name

        if incident.get("assignment_group", None) is None:
            val = self.known_assignment_groups.get(default_assignment_group) or self.load_assignment_group(default_assignment_group)
            if val:
                incident["assignment_group"] = val.get("sys_id", None)
                incident["description"] += default_assignment_group

        if cmdb_ci:
            val = self.get_cmdb_ci_table(cmdb_ci)
            if val:
                incident["cmdb_ci"] = val.get("sys_id", None)
        response = self._session.post(f'{self.url}/api/now/table/incident', headers=self.headers_api, data=json.dumps(incident, indent=4))
        try:
            return response.json(), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code


    def update_change_request(self, sys_id: str, change_request: dict):
        """
        Returns the Change Request updated response code. Response code 2XX is a success, everything else is a failure
        param:
        dict :
        {
            "short_description": "title of the change request ticket",
            "description": "description for the ticket",
            "u_approval_group": "group to approve the ticket",
            "assignment_group": "assigned group",
            "backout_plan": "rollback plan if change fails",
            "assigned_to": "email of the assigned user",
            "u_jira_url": "jira url",
            "change_plan": "Deployment plan",
            "start_date": "start date of deployment",
            'u_critical_service_affected': 'servie affected by the change',
            'risk': likelihood of interruption or failure of service to end systems,
            'impact': 'overall effect the change will have on production systems',
            'end_date': "end date of deployment",
            'test_plan': 'Pre and Post Deployment Test Plans'
        }
        sys_id : sys_id of the change request to be updated
        """

        response = self._session.patch(f'{self.url}/api/now/table/change_request/{sys_id}', headers=self.headers_api,
                                      data=json.dumps(change_request, indent=4))

        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code


    def create_change_request(self, change_request: dict):
        """
        Returns the Change Request created response code. Response code 2XX is a success, everything else is a failure
        dict :
        {
            "short_description": "title of the change request ticket",
            "description": "description for the ticket",
            "u_approval_group": "group to approve the ticket",
            "assignment_group": "assigned group",
            "backout_plan": "rollback plan if change fails",
            "assigned_to": "email of the assigned user",
            "u_jira_url": "jira url",
            "change_plan": "Deployment plan",
            "start_date": "start date of deployment",
            'u_critical_service_affected': 'servie affected by the change',
            'risk': likelihood of interruption or failure of service to end systems,
            'impact': 'overall effect the change will have on production systems',
            'end_date': "end date of deployment",
            'test_plan': 'Pre and Post Deployment Test Plans'
        }
        """

        response = self._session.post(f'{self.url}/api/now/table/change_request', headers=self.headers_api, data=json.dumps(change_request, indent=4))
        try:
            return response.json(), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code

    def create_incident_with_ci(
        self, incident: dict, assignment_group_name: str, cmdb_ci: str = None, default_assignment_group: str = 'DnA_Ops_Support_Group'
    ):
        """Returns the Incident created response code. Response code 201 is a success, everything else is a failure"""

        if assignment_group_name:
            val = self.known_assignment_groups.get(assignment_group_name) or self.load_assignment_group(assignment_group_name)
            if val:
                incident["assignment_group"] = val.get("sys_id", None)
                incident["description"] += assignment_group_name

        if incident.get("assignment_group", None) is None:
            val = self.known_assignment_groups.get(default_assignment_group) or self.load_assignment_group(default_assignment_group)
            if val:
                incident["assignment_group"] = val.get("sys_id", None)
                incident["description"] += default_assignment_group

        if cmdb_ci:
            incident["cmdb_ci"] = cmdb_ci
        response = self._session.post(f'{self.url}/api/now/table/incident', headers=self.headers_api, data=json.dumps(incident, indent=4))
        try:
            return response.json(), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code

    def get_incident(self, sys_id: str = None, number: str = None):
        """Returns the Incident. Response code 200 is a success, everything else is a failure"""

        res, response_code = self.get_table_with_offset(table="incident", name=number, sys_id=sys_id, rows=1, name_override="number")
        if response_code==200 and res.get("result"):
            if sys_id is None:
                results = list(res.get("result"))
                if(len(results) > 0):
                    return results[0], response_code;
            else:
                return res.get("result"), response_code
        return dict(), response_code

    def ci_register_dag(self, dag: dict, status: str, assignment_group_name: str):
        """Registers the DAG as CI. Response code 201 is a success, everything else is a failure"""

        if status:
            val = self.known_ci_cmdb_status.get(status) or self.load_cmdb_ci_status(status)
            if val:
                dag["u_cmdb_ci_status"] = val.get("sys_id", None)
        if assignment_group_name:
            val = self.known_assignment_groups.get(assignment_group_name) or self.load_assignment_group(assignment_group_name)
            if val:
                dag["assignment_group"] = val.get("sys_id", None)

        default_dag = dict(
            sys_domain_path = "/",
            sys_class_name = "cmdb_ci",
            u_requires_validation = "false",
            unverified = "false",
            sys_domain = "global",
            u_is_peripheral = "false",
            attestation_status = "Not Yet Reviewed",
            monitor = "false",
        )

        update_dag = dict(list(default_dag.items()) + list(dag.items()))
        try:
            data = json.dumps(update_dag, indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.post(f'{self.url}/api/now/table/cmdb_ci', data=data, headers=self.headers_api)
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code

    def get_incident_dna_open(self):
        url = f'{self.url}/api/now/table/incident?category=dna_incident&state=1'
        response = self._session.get(url, headers=self.headers_api)
        try:
            ret = response.json()
            if ret.get("result"):
                return ret.get("result"), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code
    
    def update_resolution_time(self, sys_id: str, u_issue_resolve: str):
        """Update Incident resolution time"""

        incident, response_code = self.get_incident(sys_id=sys_id)
        if incident == None:
            return
        try:
            data = json.dumps(dict({"u_issue_resolve": u_issue_resolve }), indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.patch(f'{self.url}/api/now/table/incident/{sys_id}', data=data,
                                    headers=self.headers_api)
        try:
            ret = response.json()
            if ret.get("result"):
                return ret.get("result"), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code

    def assign_incident_to(self, sys_id: str, assignment_group_name: str):
        """Assigns incident to a group"""

        incident, response_code = self.get_incident(sys_id=sys_id)
        if incident == None:
            return
        val = self.known_assignment_groups.get(assignment_group_name) or self.load_assignment_group(assignment_group_name)
        if val:
            try:
                data = json.dumps(dict({"assignment_group": val.get("sys_id", None) }), indent=4)
            except ValueError:
                raise ParameterError
            response = self._session.patch(f'{self.url}/api/now/table/incident/{sys_id}', data=data,
                                       headers=self.headers_apis)
            try:
                ret = response.json()
                if ret.get("result"):
                    return ret.get("result"), response.status_code
            except (ValueError,AttributeError):
                return response

    def incident_change_state(self, sys_id: str, state: IncidentState):
        """Changes incident state"""

        incident, response_code = self.get_incident(sys_id=sys_id)
        if incident == None:
            return
        try:
            data = json.dumps(dict({"state": state.value }), indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.patch(f'{self.url}/api/now/table/incident/{sys_id}', data=data,
                                    headers=self.headers_api)
        try:
            ret = response.json()
            if ret.get("result"):
                return ret.get("result"), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code

    def incident_append_description(self, sys_id: str, description: str):
        """Appends description to an incident"""

        incident, response_code = self.get_incident(sys_id=sys_id)
        if incident == None:
            return
        try:
            current_description = incident.get("description")
            new_description = f"{current_description}\n\nUpdate:\n=======\n{description}\n"
            data = json.dumps(dict({"description": new_description }), indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.patch(f'{self.url}/api/now/table/incident/{sys_id}', data=data,
                                    headers=self.headers_api)
        try:
            ret = response.json()
            if ret.get("result"):
                return ret.get("result"), response.status_code
        except (ValueError,AttributeError):
            return response, response.status_code

    def incident_append_note(self, sys_id: str, note: str):
        """Appends a note to an incident"""

        request = dict(
            {"comments": {"Note":note}}
        )
        try:
            data = json.dumps(request, indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.patch(f'{self.url}/api/now/table/incident/{sys_id}', data=data, headers=self.headers_api)
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code

    def incident_append_dna_info(self, number: str, dna_variables: dict):
        """Appends DnA Data to a Incident Number
        Sample variables object as per currently deployed ServiceNow DnA form:
        {
            "impacted_data_set_tier": "tier2",
            "impact": 1, //HIGH=1, Medium=2, Low=3
            "jira_issue_required_yes_no": "No",
            "data_producer_information": "UIP",
            "email_address": "noname@godaddy.com",
            "error_message_upload_any_logs_copy_paste_error_message": "ERROR_MESSAGE_LINE1\nERROR_MESSAGE_LINE2",
            "impact_description": "IMPACT_MESSAGE_LINE1\nIMPACT_MESSAGE_LINE2",
            "enter_impacted_area": "IMPACT AREA",
            "data_set_name": "DS_NAME",
            "select_team": "DRI",
            "details_of_the_issue": "DET_MESSAGE_LINE1\nDET_MESSAGE_LINE2",
            "which_area_is_impacted": "Data Issue"
        }
        """

        request = dict(
            {"variables": dna_variables}
        )
        try:
            data = json.dumps(request, indent=4)
        except ValueError:
            raise ParameterError
        response = self._session.put(f'{self.url}/api/gmi/variable_updater/{number}', data=data, headers=self.headers_api)
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code


    def create_incident_and_dna_form(
        self, incident: dict, dna_form: dict, assignment_group_name: str, cmdb_ci_name: str = None, default_assignment_group: str = 'DnA_Ops_Support_Group'
    ):
        """Returns the Incident created response and response code, dna form created response and response code.
        For Incidence, Response code 201 is a success, everything else is a failure
        For DnA Form, Response code 200 is a success, everything else is a failure"""
        inc_response, inc_response_code = self.create_incident(incident, assignment_group_name, cmdb_ci_name, default_assignment_group)
        dna_response_code = None
        dna_response = None
        if inc_response_code == 201:
            dna_response, dna_response_code = self.incident_append_dna_info(inc_response['result']['number'], dna_form)
        return inc_response, inc_response_code, dna_response, dna_response_code

    def table_write_op_by_sysid(self, table, sys_id, data, method):
        try:
            data = json.dumps(data, indent=4)
        except ValueError:
            raise ParameterError
        if method == "PUT":
            response = self._session.put(
                f"{self.url}/api/now/table/{table}/{sys_id}",
                data=data,
                headers=self.headers_api,
            )
        elif method == "DELETE":
            response = self._session.delete(
                f"{self.url}/api/now/table/{table}/{sys_id}", headers=self.headers_api
            )
        elif method == "PATCH":
            response = self._session.patch(
                f"{self.url}/api/now/table/{table}/{sys_id}",
                data=data,
                headers=self.headers_api,
            )
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code

    def get_table_dict(
            self,
            table: str,
            sys_id: str = None,
            name: str = None,
            rows: int = 1,
            name_override: str = None,
            offset: int = 0,
            extra_params_dict: dict = None,
    ):
        """Returns the table and a response code. Response code 200 is success, everything else is a failure"""

        query_path = table
        if sys_id:
            query_path = f"{query_path}/{sys_id}"
        if name:
            name_str = str(name)
            name_encoded = quote_plus(name_str) if name else None
        key = name_override if name_override else "name"
        print(
            f"{self.url}/api/now/table/{query_path}?sysparm_limit={rows}&sysparm_offset={offset}"
        )
        url = f"{self.url}/api/now/table/{query_path}?sysparm_limit={rows}&sysparm_offset={offset}"
        if name:
            url = f"{url}&{key}={name_encoded}"

        if extra_params_dict:
            for key, value in extra_params_dict.items():
                quoted_value = quote_plus(value)
                url = f"{url}&{key}={quoted_value}"
        print(f"URL: {url}")
        response = self._session.get(url, headers=self.headers_api)
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code

    def table_write_op(self, table: str, record: dict, op: str):
        try:
            data = json.dumps(record, indent=4)
        except ValueError:
            raise ParameterError
        print(f"{op} {self.url}/api/now/table/{table}")
        print(json.dumps(data))
        if op == "PUT":
            response = self._session.put(
                f"{self.url}/api/now/table/{table}", data=data, headers=self.headers_api
            )
        elif op == "POST":
            response = self._session.post(
                f"{self.url}/api/now/table/{table}", data=data, headers=self.headers_api
            )
        elif op == "DELETE":
            response = self._session.delete(
                f"{self.url}/api/now/table/{table}", data=data, headers=self.headers_api
            )
        try:
            return response.json(), response.status_code
        except (ValueError, AttributeError):
            return response, response.status_code

    def create_relationship(self, data_processor_sys_id, table_sys_id, relationship_type_object):
        try:
            logger.info(
                f"Creating relationship between {data_processor_sys_id} and {table_sys_id} and {relationship_type_object.name}"
            )
            # pipeline_ci = DataProcessor.from_cmdb(sys_id=pipeline_sys_id)
            # table_ci = Table.from_cmdb_by_sysid(sys_id=table_sys_id)
            #
            # relationship_type = CIRelationshipType.from_cmdb(name=relationship_type_name)
            # logger.info(
            #     f"Creating relationship between {pipeline_ci.name} and {table_ci.name}==here"
            # )
            relationship = None
            if relationship_type_object.name == read_relationship_type_name:
                relationship = CIRelationship.create(
                    parent_sys_id=table_sys_id, relationship_type=relationship_type_object, child_sys_id=data_processor_sys_id
                )
            elif relationship_type_object.name == write_relationship_type_name:
                relationship = CIRelationship.create(
                    parent_sys_id=data_processor_sys_id, relationship_type=relationship_type_object, child_sys_id=table_sys_id
                )

            logger.info(
                f"Created relationship in CMDB: with sys_id {relationship.sys_id}"
            )
            return relationship.sys_id
        except Exception as e:
            logger.exception(f"Error creating relationship in CMDB: {e}")




    def create_snow_cmdb_processor_entry(
            self,
            short_description,
            dag_id,
            data_processor_environment,
    ):
        try:
            logger.info(f"Creating new data processor in ServiceNow CMDB with name {dag_id}.")
            created_processor = DataProcessor.create(
                name=dag_id,
                short_description=short_description,
                pipeline_id=dag_id,
                pipeline_version="1.0",
                processor_type="airflow",
                data_processor_environment=data_processor_environment,
            )

            return created_processor.sys_id
        except DataProcessorAlreadyExists as e:
            logger.info(
                f"Processor {dag_id} already exists in ServiceNow CMDB. Fetching sys_id."
            )
            return str(e)

        except Exception as e:
            logger.exception(f"Error while creating data processor in ServiceNow CMDB: {e}")
            return str(e)

    def get_article(
            self,
            params: str
    ) -> dict[str, any]:
        """
        Get a specific knowledge article by ID.

        Args:
            config: Server configuration.
            auth_manager: Authentication manager.
            params: Parameters for getting the article.

        Returns:
            Dictionary with article details.
        """
        api_url = f"{self.url}/api/now/table/kb_knowledge/{params}"

        # Build query parameters
        query_params = {
            "sysparm_display_value": "true",
        }

        # Make request
        try:
            print(api_url)
            response = requests.get(
                api_url,
                params=query_params,
                headers=self.headers_api,
                timeout=5,
            )
            response.raise_for_status()

            # Get the JSON response
            json_response = response.json()

            # Safely extract the result
            if isinstance(json_response, dict) and "result" in json_response:
                result = json_response.get("result", {})
            else:
                logger.error("Unexpected response format: %s", json_response)
                return {
                    "success": False,
                    "message": "Unexpected response format",
                }

            if not result or not isinstance(result, dict):
                return {
                    "success": False,
                    "message": f"Article with ID {params.article_id} not found",
                }

            # Extract values safely
            article_id = result.get("sys_id", "")
            title = result.get("short_description", "")
            text = result.get("text", "")

            # Extract nested values safely
            knowledge_base = ""
            if isinstance(result.get("kb_knowledge_base"), dict):
                knowledge_base = result["kb_knowledge_base"].get("display_value", "")

            category = ""
            if isinstance(result.get("kb_category"), dict):
                category = result["kb_category"].get("display_value", "")

            workflow_state = ""
            if isinstance(result.get("workflow_state"), dict):
                workflow_state = result["workflow_state"].get("display_value", "")

            author = ""
            if isinstance(result.get("author"), dict):
                author = result["author"].get("display_value", "")

            keywords = result.get("keywords", "")
            article_type = result.get("article_type", "")
            views = result.get("view_count", "0")
            created = result.get("sys_created_on", "")
            updated = result.get("sys_updated_on", "")

            article = {
                "id": article_id,
                "title": title,
                "text": text,
                "knowledge_base": knowledge_base,
                "category": category,
                "workflow_state": workflow_state,
                "created": created,
                "updated": updated,
                "author": author,
                "keywords": keywords,
                "article_type": article_type,
                "views": views,
            }
            print(f"article: {article.get('id', '')}")
            return {
                "success": True,
                "message": "Article retrieved successfully",
                "article": article,
            }

        except requests.RequestException as e:
            logger.error(f"Failed to get article: {e}")
            return {
                "success": False,
                "message": f"Failed to get article: {str(e)}",
            }

    def list_articles(
            self,
            params: dict,
    ) -> dict[str, any]:
        """
        List knowledge articles with filtering options.

        Args:
            config: Server configuration.
            auth_manager: Authentication manager.
            params: Parameters for listing articles.

        Returns:
            Dictionary with list of articles and metadata.
        """
        try:
            logger.info(f"Starting list_articles with params: {params}")
            api_url = f"{self.url}/api/now/table/kb_knowledge"

        # Build query parameters
        query_params = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_display_value": "all",
        }

        # Build query string
        query_parts = []
        if params.knowledge_base:
            query_parts.append(f"kb_knowledge_base.sys_id={params.knowledge_base}")
        if params.category:
            query_parts.append(f"kb_category.sys_id={params.category}")
        if params.workflow_state:
            query_parts.append(f"workflow_state={params.workflow_state}")
        if params.query:
            query_parts.append(f"short_descriptionLIKE{params.query}^ORtextLIKE{params.query}")

        if query_parts:
            query_string = "^".join(query_parts)
            logger.debug(f"Constructed article query string: {query_string}")
            query_params["sysparm_query"] = query_string

        # Log the query parameters for debugging
        logger.debug(f"Listing articles with query params: {query_params}")
        # Make request
        try:
            logger.info(f"Making request to: {api_url}")
            logger.info(f"Query params: {query_params}")
            
            response = requests.get(
                api_url,
                params=query_params,
                headers=self.headers_api,
                timeout=30,  # Increased timeout from 5 to 30 seconds
            )
            response.raise_for_status()

            # Get the JSON response
            json_response = response.json()
            logger.info(f"Article listing raw response keys: {list(json_response.keys()) if isinstance(json_response, dict) else 'Not a dict'}")
            logger.info(f"Article listing raw response result count: {len(json_response.get('result', [])) if isinstance(json_response, dict) else 'No result key'}")

            # Safely extract the result
            if isinstance(json_response, dict) and "result" in json_response:
                result = json_response.get("result", [])
            else:
                logger.error("Unexpected response format: %s", json_response)
                return {
                    "success": False,
                    "message": f"Unexpected response format",
                    "articles": [],
                    "count": 0,
                    "limit": params.limit,
                    "offset": params.offset,
                }

            # Sanitize HTML content in articles to prevent JSON parsing issues
            articles = []
            
            # Handle different response formats
            if isinstance(result, list):
                articles_data = result
            elif isinstance(result, dict) and 'result' in result:
                articles_data = result['result']
            else:
                articles_data = []
            
            if isinstance(articles_data, list):
                for article_item in articles_data:
                    if not isinstance(article_item, dict):
                        continue
                    
                    # Create a copy of the article
                    sanitized_article = article_item.copy()
                    
                    # Extract key article information for better response
                    article_info = {
                        'sys_id': sanitized_article.get('sys_id', {}).get('value', ''),
                        'number': sanitized_article.get('number', {}).get('value', ''),
                        'short_description': sanitized_article.get('short_description', {}).get('value', ''),
                        'description': sanitized_article.get('description', {}).get('value', ''),
                        'workflow_state': sanitized_article.get('workflow_state', {}).get('value', ''),
                        'active': sanitized_article.get('active', {}).get('value', ''),
                        'published': sanitized_article.get('published', {}).get('value', ''),
                        'author': sanitized_article.get('author', {}).get('display_value', ''),
                        'kb_knowledge_base': sanitized_article.get('kb_knowledge_base', {}).get('display_value', ''),
                        'category': sanitized_article.get('kb_category', {}).get('display_value', ''),
                        'sys_created_on': sanitized_article.get('sys_created_on', {}).get('value', ''),
                        'sys_updated_on': sanitized_article.get('sys_updated_on', {}).get('value', ''),
                    }
                    
                    # Sanitize HTML content in text field
                    if 'text' in sanitized_article and isinstance(sanitized_article['text'], dict):
                        text_content = sanitized_article['text'].get('value', '')
                        if text_content:
                            # Remove HTML tags and clean up the content
                            import re
                            # Remove HTML tags
                            clean_text = re.sub(r'<[^>]+>', '', text_content)
                            # Remove extra whitespace and newlines
                            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                            # Limit length to prevent huge responses
                            if len(clean_text) > 1000:
                                clean_text = clean_text[:1000] + "..."
                            sanitized_article['text']['value'] = clean_text
                            sanitized_article['text']['display_value'] = clean_text
                            article_info['text'] = clean_text
                            print(f"DEBUG: Sanitized text from {len(text_content)} to {len(clean_text)} chars")
                    
                    # Add the article info to the sanitized article
                    sanitized_article['article_info'] = article_info
                    articles.append(sanitized_article)

            logger.info(f"Returning {len(articles)} articles from list_articles")
            return {
                "success": True,
                "message": f"Found {len(articles)} articles",
                "articles": articles,
                "count": len(articles),
                "limit": params.limit,
                "offset": params.offset,
            }

        except requests.RequestException as e:
            logger.error(f"Failed to list articles: {e}")
            return {
                "success": False,
                "message": f"Failed to list articles: {str(e)}",
                "articles": [],
                "count": 0,
                "limit": params.limit,
                "offset": params.offset,
            }
        except Exception as e:
            logger.error(f"Unexpected error in list_articles: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}",
                "articles": [],
                "count": 0,
                "limit": params.limit,
                "offset": params.offset,
            }

    def list_knowledge_bases(
            self,
            params: dict,
    ) -> dict[str, any]:
        """
        List knowledge bases with filtering options.

        Args:
            config: Server configuration.
            auth_manager: Authentication manager.
            params: Parameters for listing knowledge bases.

        Returns:
            Dictionary with list of knowledge bases and metadata.
        """
        api_url = f"{self.url}/api/now/table/kb_knowledge_base"

        # Build query parameters
        query_params = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_display_value": "true",
        }

        # Build query string
        query_parts = []
        if params.active is not None:
            query_parts.append(f"active={str(params.active).lower()}")
        if params.query:
            query_parts.append(f"titleLIKE{params.query}^ORdescriptionLIKE{params.query}")

        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        # Make request
        try:
            response = requests.get(
                api_url,
                params=query_params,
                headers=self.headers_api,
                timeout=5,
            )
            response.raise_for_status()

            # Get the JSON response
            json_response = response.json()

            # Safely extract the result
            if isinstance(json_response, dict) and "result" in json_response:
                result = json_response.get("result", [])
            else:
                logger.error("Unexpected response format: %s", json_response)
                return {
                    "success": False,
                    "message": "Unexpected response format",
                    "knowledge_bases": [],
                    "count": 0,
                    "limit": params.limit,
                    "offset": params.offset,
                }

            # Transform the results - create a simpler structure
            knowledge_bases = []

            # Handle either string or list
            if isinstance(result, list):
                for kb_item in result:
                    if not isinstance(kb_item, dict):
                        logger.warning("Skipping non-dictionary KB item: %s", kb_item)
                        continue

                    # Safely extract values
                    kb_id = kb_item.get("sys_id", "")
                    title = kb_item.get("title", "")
                    description = kb_item.get("description", "")

                    # Extract nested values safely
                    owner = ""
                    if isinstance(kb_item.get("owner"), dict):
                        owner = kb_item["owner"].get("display_value", "")

                    managers = ""
                    if isinstance(kb_item.get("kb_managers"), dict):
                        managers = kb_item["kb_managers"].get("display_value", "")

                    active = False
                    if kb_item.get("active") == "true":
                        active = True

                    created = kb_item.get("sys_created_on", "")
                    updated = kb_item.get("sys_updated_on", "")

                    knowledge_bases.append({
                        "id": kb_id,
                        "title": title,
                        "description": description,
                        "owner": owner,
                        "managers": managers,
                        "active": active,
                        "created": created,
                        "updated": updated,
                    })
            else:
                logger.warning("Result is not a list: %s", result)

            return {
                "success": True,
                "message": f"Found {len(knowledge_bases)} knowledge bases",
                "knowledge_bases": knowledge_bases,
                "count": len(knowledge_bases),
                "limit": params.limit,
                "offset": params.offset,
            }

        except requests.RequestException as e:
            logger.error(f"Failed to list knowledge bases: {e}")
            return {
                "success": False,
                "message": f"Failed to list knowledge bases: {str(e)}",
                "knowledge_bases": [],
                "count": 0,
                "limit": params.limit,
                "offset": params.offset,
            }
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global code
        self.close_connection = True
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if not query['state'] or query['state'][0] != state:
            raise RuntimeError("state argument missing or invalid")
        code = query['code']
