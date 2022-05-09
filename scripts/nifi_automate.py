import base64
import csv
import logging
import time

import nipyapi
import urllib3
from nipyapi.nifi import ParameterContextEntity, ParameterContextDTO, ParameterDTO, ParameterEntity

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.getLogger('nipyapi.utils').setLevel(logging.INFO)
logging.getLogger('nipyapi.security').setLevel(logging.INFO)
logging.getLogger('nipyapi.versioning').setLevel(logging.INFO)

urllib3.disable_warnings()

nipyapi.config.nifi_config.host = 'https://NIFIHOST/nifi-api'
nipyapi.config.global_ssl_verify = False
nipyapi.config.nifi_config.verify_ssl = False
nipyapi.config.default_nifi_username = 'NIFIUSER'
nipyapi.config.default_nifi_password = 'NIFIPASSWORD'

pg_lookup_id = {}
pg_lookup_name = {}
pc_lookup_id = {}
pc_lookup_name = {}


def nifi_login():
    loggedin = False
    i = 0
    attempts = 3
    delay = 10
    while (i < attempts) and (loggedin is False):
        log.info("Logging in. Attempt: " + str(i))
        loggedin = nipyapi.security.service_login(bool_response=True)
        if loggedin is False:
            time.sleep(delay)
            i = i + 1
    return loggedin


def init_lookups():
    root_pg_id = nipyapi.canvas.get_root_pg_id()
    pg_list = nipyapi.canvas.list_all_process_groups(root_pg_id)
    for pg in pg_list:
        pg_lookup_id[pg.component.id] = {'name': pg.component.name, 'parent_group_id': pg.component.parent_group_id}
        if pg.component.parameter_context is not None:
            pg_lookup_id[pg.component.id]['parameter_context_id'] = pg.component.parameter_context.component.id
        pg_lookup_name.setdefault(pg.component.name, []).append(pg.component.id)

    param_contexts = nipyapi.nifi.FlowApi().get_parameter_contexts()
    for param_context in param_contexts.parameter_contexts:
        pc_lookup_id[param_context.component.id] = param_context.component.name
        pc_lookup_name[param_context.component.name] = param_context.component.id


def check_unique_pg_group_name(name):
    if name not in pg_lookup_name or len(pg_lookup_name[name]) > 1:
        return False
    else:
        return True


def empty_queues(app):
    if not check_unique_pg_group_name(app):
        raise Exception('Process group ' + str(app) + ' is not unique')
    app_pg_groups = nipyapi.canvas.list_all_process_groups(pg_lookup_name[app][0])
    # Disable controllers, process groups and empty queues
    for app_pg_group in app_pg_groups:
        log.info("Remove all messages on connection queues of: " + str(app_pg_group.component.name))
        for con in nipyapi.canvas.list_all_connections(app_pg_group.id, True):
            if (con.status.aggregate_snapshot.queued_count is not '0'):
                log.info("Empty queue: " + str(con.id))
                mycon = nipyapi.nifi.ConnectionsApi().get_connection(con.id)
                oldexp = mycon.component.flow_file_expiration
                mycon.component.flow_file_expiration = '1 sec'
                nipyapi.nifi.ConnectionsApi().update_connection(con.id, mycon)
                time.sleep(10)
                mycon.component.flow_file_expiration = oldexp
                nipyapi.nifi.ConnectionsApi().update_connection(con.id, mycon)


def enable_proc(app):
    if not check_unique_pg_group_name(app):
        raise Exception('Process group ' + str(app) + ' is not unique')
    app_pg_groups = nipyapi.canvas.list_all_process_groups(pg_lookup_name[app][0])
    # Enable controllers and process groups
    for app_pg_group in app_pg_groups:
        log.info("Enabling controllers for: " + str(app_pg_group.component.name))
        acse = nipyapi.nifi.ActivateControllerServicesEntity()
        acse.state = "ENABLED"
        acse.id = app_pg_group.id
        nipyapi.nifi.FlowApi().activate_controller_services(id=app_pg_group.id, body=acse)
        log.info("Enabling process group: " + str(app_pg_group.component.name))
        nipyapi.canvas.schedule_process_group(app_pg_group.id, True)


def get_unused_controller_services(app):
    if not check_unique_pg_group_name(app):
        raise Exception('Process group ' + str(app) + ' is not unique')
    app_pg = nipyapi.canvas.get_process_group(identifier_type='id', identifier=pg_lookup_name[app][0])
    # Enable controllers and process groups
    cs = nipyapi.nifi.FlowApi().get_controller_services_from_group(id=app_pg.id, include_ancestor_groups=False,
                                                                   include_descendant_groups=True).controller_services
    for service in cs:
        if len(service.component.referencing_components) == 0:
            print("Controller service " + str(service.component.name) + " has no referencing components. Parent pg: " +
                  pg_lookup_id[service.component.parent_group_id]['name'])


def get_unused_parameters(app):
    if not check_unique_pg_group_name(app):
        raise Exception('Process group ' + str(app) + ' is not unique')
    app_pg_groups = nipyapi.canvas.list_all_process_groups(pg_lookup_name[app][0])
    # Enable controllers and process groups
    for pg in app_pg_groups:
        if (pg.parameter_context is not None):
            # print("Processing: "+ str(pg.parameter_context.component.name))
            param_context = nipyapi.nifi.ParameterContextsApi().get_parameter_context(pg.parameter_context.component.id)
            params = param_context.component.parameters
            for param in params:
                if len(param.parameter.referencing_components) == 0:
                    print("Context: " + str(pg.parameter_context.component.name) + ". Parameter: " + str(
                        param.parameter.name) + " is not being used")
                if param.parameter.sensitive is True and param.parameter.value is None:
                    print("Context: " + str(pg.parameter_context.component.name) + ". Sensitive parameter " + str(
                        param.parameter.name) + " has no value set")
        else:
            print("Process group: " + str(pg.component.name) + " has no parameter context assigned")


def export_parameters(filename):
    param_contexts = nipyapi.nifi.FlowApi().get_parameter_contexts()
    with open(filename, 'a') as file:
        for param_context in param_contexts.parameter_contexts:
            params = param_context.component.parameters
            for param in params:
                if len(param.parameter.referencing_components) > 0 and param.parameter.inherited is None:
                    paramvalue = param.parameter.value
                    paramtype = "Text"
                    if param.parameter.sensitive:
                        paramtype = "Sensitive"
                    elif paramvalue is None:
                        paramtype = "None"
                    elif "\"" in paramvalue or "\n" in paramvalue:
                        paramtype = "Base64"
                        paramvalue_bytes = paramvalue.encode(encoding='UTF-8', errors='strict')
                        base64_bytes = base64.b64encode(paramvalue_bytes)
                        paramvalue = base64_bytes.decode('UTF-8')
                    file.write("\"" + str(param_context.component.name) + "\",\"" + str(
                        param.parameter.name) + "\",\"" + str(paramtype) + "\",\"" + str(paramvalue) + "\"\n")


def context_exists(context_name):
    if context_name in pc_lookup_name:
        return True
    else:
        return False


def import_parameters(filename):
    with open(filename, newline='') as csvfile:
        paramreader = csv.DictReader(csvfile, fieldnames=['context', 'name', 'type', 'value'], delimiter=",",
                                     quotechar="\"")
        for paramline in paramreader:
            # create the parameter context if needed
            if not context_exists(paramline['context']):
                # nipyapi.parameters.create_parameter_context(paramline['context'])
                myparamcontext = ParameterContextEntity(revision=nipyapi.nifi.RevisionDTO(version=0),
                                                        component=ParameterContextDTO(description=None, parameters=[],
                                                                                      name=paramline['context']))
                newparamcontext = nipyapi.nifi.ParameterContextsApi().create_parameter_context(body=myparamcontext)
                print("Created context " + str(paramline['context']))
                pc_lookup_name[newparamcontext.component.name] = newparamcontext.component.id
                pc_lookup_id[newparamcontext.component.id] = newparamcontext.component.name
            # at this point we know the parameter context exists
            param_context = nipyapi.nifi.ParameterContextsApi().get_parameter_context(
                id=pc_lookup_name[paramline['context']])
            param_exists = False
            for param_obj in param_context.component.parameters:
                if paramline['name'] == param_obj.parameter.name:
                    param_exists = True
                    # print(str(param_context))
                    log.info("Parameter: " + str(
                        paramline['name'] + " in " + str(paramline['context'])) + " already exists. Not overwriting")
                    break
            if not param_exists:
                # create param
                if paramline['type'] == 'Sensitive':
                    myparam = ParameterDTO(name=paramline['name'], sensitive=True, value=paramline['value'],
                                           description='', referencing_components=[])
                elif paramline['type'] == 'Text':
                    myparam = ParameterDTO(name=paramline['name'], sensitive=False, value=paramline['value'],
                                           description='', referencing_components=[])
                elif paramline['type'] == 'Base64':
                    base64_bytes = base64.b64decode(paramline['value'].encode(encoding='UTF-8', errors='strict'))
                    paramvalue = base64_bytes.decode(encoding='UTF-8', errors='strict')
                    myparam = ParameterDTO(name=paramline['name'], sensitive=False, value=paramvalue, description='',
                                           referencing_components=[])
                elif paramline['type'] == 'None':
                    myparam = ParameterDTO(name=paramline['name'], sensitive=False, value=None, description='',
                                           referencing_components=[])
                # print("From " + str(param_context))
                parament = ParameterEntity()
                parament.parameter = myparam
                parament.can_write = True
                param_context.component.parameters.append(parament)
                log.info("Adding parameter: " + str(paramline['name']) + " in " + str(paramline['context']))
                # print("To " + str(param_context))
                nipyapi.nifi.ParameterContextsApi().submit_parameter_context_update(context_id=param_context.id,
                                                                                    body=param_context)


if __name__ == '__main__':
    log.info("Logged in: " + str(nifi_login()))
    init_lookups()
    # export_parameters('export.csv')
    import_parameters('export.csv')
