#
# Authors: Roy Dragseth (roy.dragseth@cc.uit.no)
#          Bas van der Vlies (basv@sara.nl)
#
# SVN INFO:
#   $Id: PBSQuery.py 368 2018-10-22 10:16:12Z bas $
#
# ruff: noqa: E501
"""
Usage: from PBSQuery import PBSQuery

This class gets the info from the pbs_server via the pbs.py module
for the several batch objects. All get..() functions return an dictionary
with id as key and batch object as value

There are four batch objects:
 - server
 - queue
 - job
 - node

Each object can be handled as an dictionary and has several member
functions. The second parameter is an python list and can be used if you
are only interested in certain resources, see example

There are the following functions for PBSQuery:
  job -
    getjob(job_id, attributes=<default is all>)
    getjobs(attributes=<default is all>)

  node -
    getnode(node_id, attributes=<default is all>)
    getnodes(attributes=<default is all>)

  queue -
    getqueue(queue_id, attributes=<default is all>)
    getqueues(attributes=<default is all>)

  server -
    get_serverinfo(attributes=<default is all>)

Here is an example how to use the module:
    from PBSQuery import PBSQuery
    p = PBSQuery()
    nodes = p.getnodes()
    for name,node in nodes.items():
        print name
        if node.is_free():
           print node, node['state']

    l = [ 'state', 'np' ]
    nodes = p.getnodes(l)
    for name,node in nodes.items():
           print node, node['state']

The parameter 'attributes' is an python list of resources that
you are interested in, eg: only show state of nodes
        l = list()
    l.append('state')
    nodes = p.getnodes(l)
"""
import re
import string
from typing import List, Optional

from . import pbs

REG_SUBRANGE = re.compile(r"^\d+(-\d+)?$")
"""
>>> b='rectime=1424696750,macaddr=40:a8:f0:2f:17:f4,cpuclock=Fixed,varattr=,jobs=419[1].master(cput=236745,energy_used=0,mem=6562224kb,vmem=7391872kb,walltime=22647,session_id=15941) 446[1].master(cput=7385,energy_used=0,mem=202936kb,vmem=368184kb,walltime=7391,session_id=30940) 446[2].master(cput=7385,energy_used=0,mem=204016kb,vmem=368184kb,walltime=7387,session_id=31168) 446[3].master(cput=7384,energy_used=0,mem=202380kb,vmem=368184kb,walltime=7387,session_id=31344) 446[4].master(cput=7384,energy_used=0,mem=204108kb,vmem=368184kb,walltime=7386,session_id=31536) 446[5].master(cput=7384,energy_used=0,mem=203940kb,vmem=368184kb,walltime=7386,session_id=31718) 446[6].master(cput=7383,energy_used=0,mem=188720kb,vmem=352608kb,walltime=7386,session_id=31904),state=free,size=456341748kb:459945088kb,netload=587288451179,gres=,loadave=18.07,ncpus=24,physmem=65850220kb,availmem=77961112kb,totmem=86821736kb,idletime=13933,nusers=1,nsessions=7,sessions=31904 31718 31536 31344 31168 30940 15941,uname=Linux node24 3.10.0 #1 SMP Wed Feb 4 08:16:54 CET 2015 x86_64,opsys=linux'
>>> c=','.join([x[1] for x in re.compile(r'((:?[^,(]+(?:\(.*?\))?))(?:,|$)').findall(b)])
>>> c == b
True

"""
REG_SPLIT_COMMA_BRACE = re.compile(r"((:?[^,(]+(?:\(.*?\))?))(?:,|$)")
"""
>>> d='jobs=419[1].master(cput=236745,energy_used=0,mem=6562224kb,vmem=7391872kb,walltime=22647,session_id=15941) 446[1].master(cput=7385,energy_used=0,mem=202936kb,vmem=368184kb,walltime=7391,session_id=30940) 446[2].master(cput=7385,energy_used=0,mem=204016kb,vmem=368184kb,walltime=7387,session_id=31168) 446[3].master(cput=7384,energy_used=0,mem=202380kb,vmem=368184kb,walltime=7387,session_id=31344) 446[4].master(cput=7384,energy_used=0,mem=204108kb,vmem=368184kb,walltime=7386,session_id=31536) 446[5].master(cput=7384,energy_used=0,mem=203940kb,vmem=368184kb,walltime=7386,session_id=31718) 446[6].master(cput=7383,energy_used=0,mem=188720kb,vmem=352608kb,walltime=7386,session_id=31904)'
>>> e='='.join([x[1] for x in re.compile(r'((:?[^=(]+(?:\(.*?\))?))(?:=|$)').findall(d)])
>>> d == e
True
"""
REG_SPLIT_EQUAL_BRACE = re.compile(r"((:?[^=(]+(?:\(.*?\))?))(?:=|$)")

JOB_RE = re.compile("(?:^|,)(?:((?:[\d,-]+)?\d+)/)?(.+)")


def convert_range(rangetxt):
    """
    Convert range string into list of id strings: eg.g '3,5,7-9' -> ['3','5','7','8','9']
    """
    ids = []
    for subrange in [r.split("-") for r in rangetxt.split(",")]:
        start = int(subrange[0])
        if len(subrange) == 2:
            end = int(subrange[1]) + 1
        else:
            end = start + 1
        ids.extend([str(i) for i in range(start, end)])
    return ids


class PBSError(Exception):
    def __init__(self, msg=""):
        self.msg = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.msg

    __str__ = __repr__


class _PBSobject(dict):
    TRUE = 1
    FALSE = 0

    def __init__(self, dictin=None):
        super().__init__(self)
        self.name = None

        if dictin:
            if "name" in dictin:
                self.name = dictin["name"]
                del dictin["name"]
            self.data = dictin

    def get_value(self, key):
        if key in self:
            return self[key]
        else:
            return None

    def __getattr__(self, name):
        """
        override the class attribute get method. Return the value
        from the dict
        """
        try:
            return self.data[name]
        except KeyError:
            error = "Attribute key error: %s" % (name)
            raise PBSError(error)

    def uniq(self, list):
        """Filter out unique items of a list"""
        uniq_items = {}
        for item in list:
            uniq_items[item] = 1
        return list(uniq_items.keys())

    def return_value(self, key):
        """Function that returns a value independent of new or old data structure"""
        if isinstance(self[key], list):
            return self[key][0]
        else:
            return self[key]


class PBSQuery:
    # a[key] = value, key and value are data type string
    #
    OLD_DATA_STRUCTURE = False

    def __init__(self, server=None):
        if not server:
            self.server = pbs.pbs_default()
        else:
            self.server = server

        self._connect()
        ## this is needed for getjob a jobid is made off:
        #    sequence_number.server (is not self.server)
        #
        self.job_server_id = list(self.get_serverinfo())[0]
        self._disconnect()

    def _connect(self):
        """Connect to the PBS/Torque server"""
        self.con = pbs.pbs_connect(self.server)
        if self.con < 0:
            str = "Could not make a connection with %s\n" % (self.server)
            raise PBSError(str)

    def _disconnect(self):
        """Close the PBS/Torque connection"""
        pbs.pbs_disconnect(self.con)
        self.attribs = "NULL"

    def _list_2_attrib(self, attrib_list: List):
        """Convert a python list to an attrib list suitable for pbs"""
        if not attrib_list:
            self.attribs = []
            return
        self.attribs = pbs.new_attrl(len(attrib_list))
        i = 0
        for attrib in attrib_list:
            # So we can user Resource
            attrib = attrib.split(".")
            self.attribs[i].name = attrib[0]
            i = i + 1

    def _pbsstr_2_list(self, pbsstr, delimiter):
        """Convert a string to a python list and use delimiter as split char"""
        tokens = pbsstr.split(delimiter)
        if len(tokens) > 1:
            return tokens

    def _list_2_dict(self, stat_list: list, obj_type: str):
        """
        Convert a pbsstat function list to a class dictionary, The
        data structure depends on the function new_data_structure().

        Default data structure is:
            class[key] = value, Where key and value are of type string

        Future release, can be set by new_data_structure():
            - class[key] = value where value can be:
              1. a list of values of type string
              2. a dictionary with as list of values of type string. If
                 values contain a '=' character

          eg:
                print node['np']
                >> [ '2' ]

                print node['status']['arch']
                >> [ 'x86_64' ]
        """
        self.d = {}
        for item in stat_list:
            new = globals()[obj_type]()
            self.d[item.name] = new
            new.name = item.name

            for a in item.attribs:
                if self.OLD_DATA_STRUCTURE:
                    if a.resource:
                        key = "%s.%s" % (a.name, a.resource)
                    else:
                        key = "%s" % (a.name)
                    new[key] = a.value
                else:
                    # Don't split , between ()
                    values = [x[1] for x in REG_SPLIT_COMMA_BRACE.findall(a.value)]
                    if len(values) == 1:
                        values = [a.value]

                    # We must creat sub dicts, only for specified
                    # key values
                    if a.name in ["status", "Variable_List"]:
                        for v in values:
                            # Don't split between ()
                            tmp_l = [x[1] for x in REG_SPLIT_EQUAL_BRACE.findall(v)]

                            ## Support for multiple EVENT mesages in format [key=value:]+
                            #  format eg: message=EVENT:sample.time=1288864220.003,EVENT:kernel=upgrade,cputotals.user=0
                            #             message=ERROR <text>
                            #
                            if tmp_l[0] in ["message"]:
                                if tmp_l[1].startswith("EVENT:"):
                                    tmp_d = dict()
                                    new["event"] = globals()[obj_type](tmp_d)

                                    message_list = v.split(":")
                                    for event_type in message_list[1:]:
                                        tmp_l = event_type.split("=")
                                        new["event"][tmp_l[0]] = tmp_l[1:]
                                else:
                                    ## ERROR message
                                    #
                                    new["error"] = tmp_l[1:]

                            elif tmp_l[0].startswith("EVENT:"):
                                message_list = v.split(":")
                                for event_type in message_list[1:]:
                                    tmp_l = event_type.split("=")
                                    new["event"][tmp_l[0]] = tmp_l[1:]

                            else:
                                ## Check if we already added the key
                                if a.name in new:
                                    new[a.name][tmp_l[0]] = tmp_l[1:]
                                else:
                                    tmp_d = dict()
                                    tmp_d[tmp_l[0]] = tmp_l[1:]
                                    new[a.name] = globals()[obj_type](tmp_d)

                    else:
                        ## Check if it is a resource type variable, eg:
                        #  - Resource_List.(nodes, walltime, ..)
                        #
                        if a.resource:
                            if a.name in new:
                                new[a.name][a.resource] = values

                            else:
                                tmp_d = dict()
                                tmp_d[a.resource] = values
                                new[a.name] = globals()[obj_type](tmp_d)
                        else:
                            # Simple value
                            #
                            new[a.name] = values
        self._free(stat_list)

    def _free(self, memory):
        """
        freeing up used memmory

        """
        pbs.pbs_statfree(memory)

    def _statserver(self, attrib_list: List = []):
        """Get the server config from the pbs server"""
        self._list_2_attrib(attrib_list)

        self._connect()
        serverinfo = pbs.pbs_statserver(self.con, self.attribs, "NULL")
        self._disconnect()

        self._list_2_dict(serverinfo, Server)

    def get_serverinfo(self, attrib_list: List = []):
        self._statserver(attrib_list)
        return self.d

    def _statqueue(self, queue_name="", attrib_list: List = []):
        """Get the queue config from the pbs server"""
        self._list_2_attrib(attrib_list)

        self._connect()
        queues = pbs.pbs_statque(self.con, queue_name, self.attribs, "NULL")
        self._disconnect()

        self._list_2_dict(queues, Queue)

    def getqueue(self, name, attrib_list: List = []):
        self._statqueue(name, attrib_list)
        try:
            return self.d[name]
        except KeyError:
            return self.d

    def getqueues(self, attrib_list: List = []):
        self._statqueue("", attrib_list)
        return self.d

    def _statnode(self, select="", attrib_list: List = [], property: Optional[str] = None):
        """Get the node config from the pbs server"""
        self._list_2_attrib(attrib_list)

        if property:
            select = f":{property}"

        self._connect()
        nodes = pbs.pbs_statnode(self.con, select, self.attribs, "NULL")
        self._disconnect()

        self._list_2_dict(nodes, Node)

    def getnode(self, name, attrib_list: List = []):
        self._statnode(name, attrib_list)
        try:
            return self.d[name]
        except KeyError:
            return self.d

    def getnodes(self, attrib_list: List = []):
        self._statnode("", attrib_list)
        return self.d

    def getnodes_with_property(self, property, attrib_list=None):
        self._statnode("", attrib_list, property)
        return self.d

    def _statjob(self, job_name="", attrib_list=[]):
        """Get the job config from the pbs server"""
        self._list_2_attrib(attrib_list)

        self._connect()
        jobs = pbs.pbs_statjob(self.con, job_name, self.attribs, "NULL")
        self._disconnect()

        self._list_2_dict(jobs, Job)

    def getjob(self, name, attrib_list=None):
        ## To make sure we use the full name of a job; Changes a name like 1234567 into 1234567.job_server_id
        if len(name.split(".")) == 1:
            name = name.split(".")[0] + "." + self.job_server_id

        self._statjob(name, attrib_list)
        try:
            return self.d[name]
        except KeyError:
            return self.d

    def getjobs(self, attrib_list=None):
        self._statjob("", attrib_list)
        return self.d

    def get_server_name(self):
        return self.server

    def new_data_structure(self):
        """
        Use the new data structure. Is now the default
        """
        self.OLD_DATA_STRUCTURE = False

    def old_data_structure(self):
        """
        Use the old data structure. This function is obselete and
        will be removed in a future release
        """
        self.OLD_DATA_STRUCTURE = True


class Job(_PBSobject):
    """PBS job class"""

    def is_running(self):
        value = self.return_value("job_state")
        if value == "Q":
            return self.TRUE
        else:
            return self.FALSE

    def get_nodes(self, unique=None):
        """
        Returns a list of the nodes which run this job
        format:
          * exec_host: gb-r10n14/5+gb-r10n14/4+gb-r10n14/3+gb-r10n14/2+gb-r10n14/1+gb-r10n14/0
          * split on '+' and if uniq is set split on '/'
        """
        nodes = self.get_value("exec_host")
        if not nodes:
            return list()

        if isinstance(nodes, str):
            nodelist = string.split(nodes, "+")
        else:
            nodelist = []
            for n in nodes:
                if REG_SUBRANGE.search(n):
                    # This is a range split by _list_2_dict in a list
                    # E.g. exec_host node1/4,5,8-9 is after _list_dict ['node1/4', '5', '8-9']
                    # Re-join them with the last node
                    nodelist[-1] += ",%s" % n
                else:
                    nodelist.extend(n.split("+"))

        res = []
        for n in nodelist:
            t = string.split(n, "/")

            if not unique:
                res.extend(["%s/%s" % (t[0], i) for i in convert_range(t[1])])
            else:
                if t[0] not in res:
                    res.append(t[0])

        return res


class Node(_PBSobject):
    """PBS node class"""

    def is_free(self):
        """Check if node is free"""

        value = self.return_value("state")
        if value == "free":
            return self.TRUE
        else:
            return self.FALSE

    def has_job(self):
        """Does the node run a job"""
        try:
            self["jobs"]
            return self.TRUE
        except KeyError:
            return self.FALSE

    def get_jobs(self, unique=None):
        """Returns a list of the currently running job-id('s) on the node"""

        jobs = self.get_value("jobs")
        if not jobs:
            return list()

        if isinstance(jobs, str):
            jlist = re.compile("[^\\ /]\\d+[^/.]").findall(jobs)

            if not unique:
                return jlist
            else:
                return self.uniq(jlist)

        else:
            # Support id ranges before job id
            joblist = []
            # Jobs might be splitted in ranges, but here _list_2_dict does
            # 1,3,7-9/jobid -> ['1','3','7-9/jobid']
            # Process in reverse order
            for j in jobs[::-1]:
                if REG_SUBRANGE.search(j):
                    joblist[-1] = "%s,%s" % (j, joblist[-1])
                else:
                    joblist.append(j)

            # extend with nodes
            all_jobs = []

            for j in joblist[::-1]:
                r = JOB_RE.search(j)
                # 1st match is range, second part is jobid
                jobstr = r.groups()[1]
                if unique:
                    if jobstr not in all_jobs:
                        all_jobs.append(jobstr)
                else:
                    all_jobs.extend(["%s/%s" % (i, jobstr) for i in convert_range(r.groups()[0])])

            return all_jobs


class Queue(_PBSobject):
    """PBS queue class"""

    def is_enabled(self):
        value = self.return_value("enabled")
        if value == "True":
            return self.TRUE
        else:
            return self.FALSE

    def is_execution(self):
        value = self.return_value("queue_type")
        if value == "Execution":
            return self.TRUE
        else:
            return self.FALSE


class Server(_PBSobject):
    """PBS server class"""

    def get_version(self):
        return self.get_value("pbs_version")


def main():
    p = PBSQuery()
    serverinfo = p.get_serverinfo()
    for server in list(serverinfo.keys()):
        print(server, " version: ", serverinfo[server].get_version())
    for resource in list(serverinfo[server].keys()):
        print("\t ", resource, " = ", serverinfo[server][resource])

    queues = p.getqueues()
    for queue in list(queues.keys()):
        print(queue)
        if queues[queue].is_execution():
            print("\t ", queues[queue])
        if "acl_groups" in queues[queue]:
            print("\t acl_groups: yes")
        else:
            print("\t acl_groups: no")

    jobs = p.getjobs()
    for name, job in list(jobs.items()):
        if job.is_running():
            print(job)

    states = ["state"]
    nodes = p.getnodes(states)
    for name, node in list(nodes.items()):
        if node.is_free():
            print(node)


if __name__ == "__main__":
    main()
