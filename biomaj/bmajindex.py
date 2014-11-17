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

    @staticmethod
    def delete_all_bank(bank_name):
      '''
      Delete complete index for a bank
      '''
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
      BmajIndex.es.delete(index=BmajIndex.index, doc_type='production', id=bank_name+'_'+release)

    @staticmethod
    def search(query):
      res = BmajIndex.es.search(index=BmajIndex.index, doc_type='production', body=query)
      return res['hits']['hits']

    @staticmethod
    def add(bank_name, prod, flush):
      '''
      Index a production release

      :param bank_name: Name of the bank
      :type bank_name: str
      :param prod: production release object
      :type prod: dict
      :param flush: Force flushing
      :type flush: bool
      '''
      if not BmajIndex.do_index:
        return
      obj = copy.deepcopy(prod)
      obj['bank'] = bank_name
      res = BmajIndex.es.index(index=BmajIndex.index, doc_type='production', id=bank_name+'_'+obj['release'], body=obj)
      if flush:
        BmajIndex.es.indices.flush(index=BmajIndex.index, force=True)
