import logging
import copy
from elasticsearch import Elasticsearch

class BmajIndex(object):
    '''
    ElasticSearch indexation and search
    '''


    '''
    ElasticSearch server
    '''
    es = None

    '''
    Index name
    '''
    index = 'biomaj'

    '''
    Do indexing
    '''
    do_index = False

    @staticmethod
    def load(hosts=['localhost'], index='biomaj', do_index=True):
      '''
      Initialize index

      :param hosts: List of elastic search nodes to connect to
      :type hosts: list
      :param do_index: index data or not
      :type do_index: bool
      '''
      if not do_index:
        return
      BmajIndex.index = index
      BmajIndex.do_index = do_index
      if BmajIndex.es is None:
        BmajIndex.es = Elasticsearch(hosts)
        mapping = {
          "mappings": {
                "production": {
                  "date_detection": False
                }
            }

        }
        if not BmajIndex.es.indices.exists(index=BmajIndex.index):
          BmajIndex.es.indices.create(index=BmajIndex.index,body=mapping)


    @staticmethod
    def delete_all_bank(bank_name):
      '''
      Delete complete index for a bank
      '''
      if not BmajIndex.do_index:
        return
      query = {
        "query" : {
          "term" : { "bank" : bank_name }
          }
        }
      BmajIndex.es.delete_by_query(index=BmajIndex.index, body=query)

    @staticmethod
    def remove(bank_name, release):
      '''
      Remove a production release

      :param bank_name: Name of the bank
      :type bank_name: str
      :param release: production release
      :type release: str
      '''
      if not BmajIndex.do_index:
        return
      try:
        BmajIndex.es.delete(index=BmajIndex.index, doc_type='production', id=bank_name+'_'+release)
      except Exception as e:
        logging.error('Index:Remove:'+bank_name+'_'+str(obj['release'])+':Exception:'+str(e))

    @staticmethod
    def search(query):
      if not BmajIndex.do_index:
        return None
      res = BmajIndex.es.search(index=BmajIndex.index, doc_type='production', body=query)
      return res['hits']['hits']

    @staticmethod
    def add(bank_name, prod, flush=False):
      '''
      Index a production release

      :param bank_name: Name of the bank
      :type bank_name: str
      :param prod: session release object
      :type prod: dict
      :param flush: Force flushing
      :type flush: bool
      '''
      if not BmajIndex.do_index:
        return
      obj = copy.deepcopy(prod)
      obj['bank'] = bank_name
      try:
        if obj['release'] is not None and obj['release'] != 'none':
          res = BmajIndex.es.index(index=BmajIndex.index, doc_type='production', id=bank_name+'_'+str(obj['release']), body=obj)
          if flush:
            BmajIndex.es.indices.flush(index=BmajIndex.index, force=True)
      except Exception as e:
        logging.error('Index:Add:'+bank_name+'_'+str(obj['release'])+':Exception:'+str(e))
