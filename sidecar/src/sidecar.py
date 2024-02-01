from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName, MetaInfo, Component, ContentType
from ndn.client_conf import default_face

import subprocess as sp
# import sys
import os
import time
import datetime
from queue import Queue
import json

from send_msg import call_service
from queue import Queue


os.environ['LOG_START_TIME'] = str(datetime.datetime.now())

service_name = Name.normalize(os.environ['MY_SERVICE_NAME'])

SERVICE_STATS_TAG = 'stats'
service_counter = Queue(maxsize=1)
service_counter.put(0)

cert_install = sp.run(
    'ndnsec key-gen $MY_SERVICE_NAME | ndnsec cert-install -', shell=True)

advertise = sp.run(
    'nlsrc -R $ROUTER_PREFIX -k advertise $MY_SERVICE_NAME', shell=True)

face_url = os.environ['NDN_CLIENT_TRANSPORT']

q = Queue(maxsize=1)
SEGMENT_SIZE = 8000
FRESHNESS_PERIOD = 5.000
TMP_PATH = os.environ['SHARE_PATH']

LOG_PATH = '/service.log'
with open(LOG_PATH, 'w'):
    pass

face = default_face(face_url)
app = NDNApp(face=face)


# stats
@app.route(service_name + Name.normalize(SERVICE_STATS_TAG))
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    print(f'>> I: {Name.to_str(name)}, {param}')

    if '/32=metadata' in Name.to_str(name):
        # version discovery process
        timestamp = int(time.time() * 1000)
        metaname = service_name + Name.normalize(SERVICE_STATS_TAG) + \
            Name.normalize('/32=metadata') + \
            [Component.from_version(timestamp)]+[Component.from_segment(0)]
        metadata = service_name + \
            Name.normalize(SERVICE_STATS_TAG) + \
            [Component.from_version(timestamp)]
        print('<< D(meta): ', Name.to_str(metaname))
        app.put_data(metaname, Name.to_bytes(metadata), freshness_period=10)
    else:
        service_count = service_counter.get()
        service_counter.put(service_count)

        service_stats = json.dumps({
            'service_name': Name.to_str(service_name),
            'service_count': service_count})
        print(f'<< D: {Name.to_str(name)}')
        app.put_data(name, content=service_stats,
                     freshness_period=100,
                     final_block_id=Component.from_segment(0))


# service
@app.route(service_name)
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    print(f'>> I: {Name.to_str(name)}, {param}')
    os.environ['LOG_SIDECAR_IN_TIME'] = str(datetime.datetime.now())

    # parse interest name
    #   name: /func/content/32=metadata/v=1234567890987/seg=0
    #   name_noseg: /func/content/32=metadata/v=1234567890987
    #   name_nosegver: /func/content
    #   trimmed_name: /content
    if Component.get_type(name[-1]) == Component.TYPE_SEGMENT:
        seg_no = Component.to_number(name[-1])
        name_noseg = name[:-1]
    else:
        name_noseg = name
        seg_no = 0
    if Component.get_type(name_noseg[-1]) == Component.TYPE_VERSION:
        name_nosegver = name_noseg[:-1]
    else:
        name_nosegver = name_noseg
    if Name.to_str(name_nosegver[-1:]) == '/32=metadata':
        if seg_no >= 1:
            print('<< NACK ', {Name.to_str(name)})
            app.put_data(name, b'', content_type=ContentType.NACK)
            return
        name_nosegver = name_nosegver[:-1]
        trimmed_name = name_nosegver[1:]
    else:
        trimmed_name = name_noseg[1:]

    # get content
    holding_content = {'name': '', 'content': b'', 'time': 0.0}
    if not q.empty():
        holding_content = q.get()
    if Name.to_str(name_nosegver) == holding_content['name'] and time.time() - holding_content['time'] <= FRESHNESS_PERIOD:
        processed_content = holding_content['content']
        q.put(holding_content)
    else:
        print(f'<< I: {Name.to_str(trimmed_name)}')
        name_message = Name.to_str(trimmed_name)[1:].replace('/', '-')
        with open(os.path.join(TMP_PATH, name_message), 'wb') as f:
            sp.run(['ndncatchunks', Name.to_str(
                trimmed_name), '-qf'], stdout=f)
        with open(os.path.join(TMP_PATH, name_message), 'r') as f:
            os.environ['IN_DATASIZE'] = str(len(f.read()))

        # service function
        t0_service = time.time()
        os.environ['LOG_SERVICE_CALL_IN_TIME'] = str(datetime.datetime.now())
        processed_content = call_service(name_message)
        dt_service = t0_service - time.time()
        os.environ['LOG_SERVICE_CALL_OUT_TIME'] = str(datetime.datetime.now())
        print('From Service, datasize: ', len(processed_content),
              'service + socket time: ', dt_service)
        holding_content = {
            'name': Name.to_str(name_nosegver),
            'content': processed_content,
            'time': time.time()
        }
        q.put(holding_content)

        service_counter.put(service_counter.get() + 1)

    # put content
    seg_cnt = (len(processed_content) + SEGMENT_SIZE - 1) // SEGMENT_SIZE
    timestamp = int(holding_content['time'] * 1000)

    if '/32=metadata' in Name.to_str(name) and seg_no < 1:
        # version discovery process
        metaname = name_nosegver + \
            Name.normalize('/32=metadata') + \
            [Component.from_version(timestamp)]+[Component.from_segment(0)]
        metadata = name_nosegver+[Component.from_version(timestamp)]
        print('<< D(meta): ', Name.to_str(metaname))
        app.put_data(metaname, Name.to_bytes(metadata), freshness_period=10)
    elif seg_no < seg_cnt:
        send_name = name_nosegver + \
            [Component.from_version(timestamp)] + \
            [Component.from_segment(seg_no)]
        print(f'<< D: {Name.to_str(send_name)}')
        app.put_data(send_name,
                     processed_content[seg_no *
                                       SEGMENT_SIZE:(seg_no+1)*SEGMENT_SIZE],
                     freshness_period=100,
                     final_block_id=Component.from_segment(seg_cnt-1))
        print(MetaInfo(freshness_period=100,
                       final_block_id=seg_cnt-1))

        os.environ['OUT_DATASIZE'] = str(len(processed_content))
        print('Content: (size:', os.environ['OUT_DATASIZE'], ')')
        print('')

        if seg_no == seg_cnt - 1:
            os.environ['LOG_SIDECAR_OUT_TIME'] = str(datetime.datetime.now())
            log_json = json.dumps({
                "sfc_time": os.environ['LOG_START_TIME'],
                "service_call": {
                    "call_name": Name.to_str(service_name),
                    "in_time": os.environ['LOG_SERVICE_CALL_IN_TIME'],
                    "out_time": os.environ['LOG_SERVICE_CALL_OUT_TIME'],
                    "port_num": 6363,
                    "in_datasize": int(os.environ['IN_DATASIZE']),
                    "out_datasize": int(os.environ['OUT_DATASIZE']),
                },
                "sidecar": {
                    "in_time": os.environ['LOG_SIDECAR_IN_TIME'],
                    "out_time": os.environ['LOG_SIDECAR_OUT_TIME'],
                    "name": "ndn-sidecar",
                    "protocol": "ndn",
                },
                "host_name": os.environ['MY_HOST_IP']})
            with open(LOG_PATH, 'a') as f:
                f.write(log_json)
                f.write('\n')
            print('updated log')


if __name__ == '__main__':
    print(f'My Service Name: {Name.to_str(service_name)}')
    print(f'Service Stats: {Name.to_str(service_name)}/{SERVICE_STATS_TAG}')
    try:
        app.run_forever()
    finally:
        sp.run('nlsrc -R $ROUTER_PREFIX -k withdraw $MY_SERVICE_NAME', shell=True)
