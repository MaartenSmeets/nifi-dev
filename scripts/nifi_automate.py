import base64
import csv
import logging
import time
import uuid

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

csv.register_dialect('params', delimiter=',', quoting=csv.QUOTE_ALL, quotechar='"')


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


def disable_proc(app):
    if not check_unique_pg_group_name(app):
        raise Exception('Process group ' + str(app) + ' is not unique')
    app_pg_groups = nipyapi.canvas.list_all_process_groups(pg_lookup_name[app][0])
    # Disable controllers, process groups and empty queues
    for app_pg_group in app_pg_groups:
        log.info("Disabling process group: " + str(app_pg_group.component.name))
        nipyapi.canvas.schedule_process_group(app_pg_group.id, False)
        # log.info("Remove all messages on connection queues of: " + str(app_pg_group.component.name))
        # nipyapi.canvas.purge_process_group(app_pg_group, stop=False)
        log.info("Disabling controllers for: " + str(app_pg_group.component.name))
        acse = nipyapi.nifi.ActivateControllerServicesEntity()
        acse.state = "DISABLED"
        acse.id = app_pg_group.id
        nipyapi.nifi.FlowApi().activate_controller_services(id=app_pg_group.id, body=acse)


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


def string_needs_encoding(check_str):
    if check_str is None:
        return False
    elif "\"" in check_str or "\n" in check_str:
        return True
    else:
        return False


def encodeBase64(input_str):
    input_bytes = input_str.encode(encoding='UTF-8', errors='strict')
    base64_bytes = base64.b64encode(input_bytes)
    return base64_bytes.decode('UTF-8')


def decodeBase64(input_str):
    base64_bytes = base64.b64decode(input_str.encode(encoding='UTF-8', errors='strict'))
    return base64_bytes.decode(encoding='UTF-8', errors='strict')


def export_parameters(filename):
    param_contexts = nipyapi.nifi.FlowApi().get_parameter_contexts()
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file, 'params')
        for param_context in param_contexts.parameter_contexts:
            params = param_context.component.parameters
            for param in params:
                param_value = param.parameter.value
                param_descr = param.parameter.description
                param_sensitive = param.parameter.sensitive
                if param_sensitive:
                    param_value = ''

                if string_needs_encoding(param_value):
                    param_value_type = 'Base64'
                    param_value = encodeBase64(param_value)
                elif param_value is None:
                    param_value_type = 'None'
                    param_value = ''
                else:
                    param_value_type = 'Text'

                if string_needs_encoding(param_descr):
                    param_descr = encodeBase64(param_descr)
                    param_descr_type = 'Base64'
                else:
                    param_descr_type = 'Text'

                writeline = [str(param_context.component.name), str(param.parameter.name), str(param_value),
                             str(param_value_type), str(param_sensitive), str(param_descr), str(param_descr_type)]
                writer.writerow(writeline)


def context_exists(context_name):
    if context_name in pc_lookup_name:
        return True
    else:
        return False


def str_to_bool(str_bool):
    if str_bool == 'True':
        return True
    else:
        return False


def create_param_entity(myparam_entity, param_props):
    param_changed = False
    if myparam_entity is None:
        log.info('Parameter entity not supplied to create_param_entity. Creating a new one')
        myparam_entity = ParameterEntity()
        myparam_entity.parameter = ParameterDTO()
        param_changed = True

    myparam_entity.parameter.name = param_props['param_name']

    if hasattr(myparam_entity.parameter, 'sensitive') and str_to_bool(
            param_props['param_sensitive']) == myparam_entity.parameter.sensitive:
        log.info(
            'Not updating sensitive property of ' + str(myparam_entity.parameter.name) + ' since its value is unchanged')
    else:
        log.info('Updating sensitive property of ' + str(myparam_entity.parameter.name) + ' to ' + str(
            param_props['param_sensitive']))
        myparam_entity.parameter.sensitive = str_to_bool(param_props['param_sensitive'])
        param_changed = True

    if param_props['param_value_type'] == 'Text':
        newvalue = param_props['param_value']
    elif param_props['param_value_type'] == 'None':
        newvalue = None
    elif param_props['param_value_type'] == 'Base64':
        newvalue = decodeBase64(param_props['param_value'])
    else:
        raise Exception('Unknown parameter type: ' + str(param_props['param_value_type']))

    if hasattr(myparam_entity.parameter, 'value') and myparam_entity.parameter.value == newvalue:
        log.info('Not updating value of ' + str(myparam_entity.parameter.name) + ' since its value is unchanged')
    else:
        log.info('Updating value of ' + str(myparam_entity.parameter.name))
        myparam_entity.parameter.value = newvalue
        param_changed = True

    if param_props['param_descr_type'] == 'Text':
        newdescription = param_props['param_descr']
    elif param_props['param_descr_type'] == 'Base64':
        newdescription = decodeBase64(param_props['param_descr'])
    else:
        raise Exception('Unknown description type: ' + str(param_props['param_descr_type']))

    if hasattr(myparam_entity.parameter, 'description') and myparam_entity.parameter.description == newdescription:
        log.info('Not updating description of ' + str(myparam_entity.parameter.name) + ' since its value is unchanged')
    else:
        log.info('Updating description of ' + str(myparam_entity.parameter.name))
        myparam_entity.parameter.description = newdescription
        param_changed = True

    if param_changed:
        log.info('Parameter ' + str(myparam_entity.parameter.name) + ' has been updated!')
    else:
        log.info('Parameter ' + str(myparam_entity.parameter.name) + ' has not been updated!')
    return param_changed, myparam_entity


def create_dummy_param_context(pc_name, pc_id):
    myparamcontext = ParameterContextEntity(revision=nipyapi.nifi.RevisionDTO(version=0),
                                            component=ParameterContextDTO(description=None, parameters=[],
                                                                          name=pc_name, id=pc_id))
    return myparamcontext


def import_parameters(filename, overwrite_existing_params, dummyrun):
    with open(filename, newline='') as csvfile:
        paramreader = csv.DictReader(csvfile, dialect='params',
                                     fieldnames=['context', 'param_name', 'param_value', 'param_value_type',
                                                 'param_sensitive', 'param_descr', 'param_descr_type'])
        for paramline in paramreader:
            # create the parameter context if needed
            param_context = None
            if not context_exists(paramline['context']):
                log.info("Context not found. Creating")
                # nipyapi.parameters.create_parameter_context(paramline['context'])

                myparamcontext = ParameterContextEntity(revision=nipyapi.nifi.RevisionDTO(version=0),
                                                        component=ParameterContextDTO(description=None, parameters=[],
                                                                                      name=paramline['context']))
                if not dummyrun:
                    # Create new context
                    param_context = nipyapi.nifi.ParameterContextsApi().create_parameter_context(body=myparamcontext)
                    log.info("Created context " + str(paramline['context']))
                else:
                    # Generate a dummy context
                    param_context = create_dummy_param_context(paramline['context'],
                                                                 str('DUMMY_') + str(uuid.uuid1()))
                    log.info("Created dummy context " + str(paramline['context']))

                pc_lookup_name[param_context.component.name] = param_context.component.id
                pc_lookup_id[param_context.component.id] = param_context.component.name
            else:
                log.info("Context found. Fetching")
                if dummyrun and pc_lookup_name[paramline['context']].startswith('DUMMY_'):
                    #we are dealing with a dummy context created in one of the earlier parameter lines
                    param_context = create_dummy_param_context(paramline['context'], pc_lookup_name[paramline['context']])
                else:
                    param_context = nipyapi.nifi.ParameterContextsApi().get_parameter_context(id=pc_lookup_name[paramline['context']])

            # at this point we know the parameter context exists

            param_done = False
            for i, param_obj in enumerate(param_context.component.parameters):
                if paramline['param_name'] == param_obj.parameter.name:
                    if not overwrite_existing_params:
                        log.info("Parameter: " + str(paramline['param_name'] + " in " + str(
                            paramline['context'])) + " already exists. Not overwriting")
                        param_done = True
                        param_changed_so_call_api = False
                        break
                    else:
                        if paramline['param_sensitive'] == 'True' and paramline['param_value'] != '':
                            log.info("Parameter: " + str(paramline['param_name'] + " will be updated in context " + str(
                                paramline['context'])) + " since it is sensitive and a value has been given")
                            update_param = True
                        elif paramline['param_sensitive'] == 'False':
                            log.info("Parameter: " + str(paramline['param_name'] + " will be updated in context " + str(
                                paramline['context'])) + " since it is not sensitive")
                            update_param = True
                        else:
                            log.info(
                                "Parameter: " + str(paramline['param_name'] + " will not be updated in context " + str(
                                    paramline['context'])) + " since it is sensitive no new value has been given")
                            update_param = False

                        if update_param:
                            param_changed_so_call_api, parament = create_param_entity(param_obj, paramline)
                            param_context.component.parameters[i] = parament
                        param_done = True
                        break

            # The parameter does not exist and needs to be created
            if not param_done:
                param_updated, parament = create_param_entity(None, paramline)
                param_changed_so_call_api = True
                param_context.component.parameters.append(parament)
                log.info("Adding parameter: " + str(paramline['param_name']) + " to " + str(paramline['context']))
                # print("To " + str(param_context))

            if param_changed_so_call_api:
                log.info("Parameter changed so calling the API to update it")
                if not dummyrun:
                    nipyapi.nifi.ParameterContextsApi().submit_parameter_context_update(context_id=param_context.id,
                                                                                        body=param_context)
                    time.sleep(3)
                else:
                    log.info("Dummy run. Not updating parameter context")
            else:
                log.info("Parameter not changed so not calling the API to update it")


if __name__ == '__main__':
    log.info("Logged in: " + str(nifi_login()))
    init_lookups()
    # export_parameters('export.csv')
    import_parameters('export.csv', overwrite_existing_params=False, dummyrun=False)
