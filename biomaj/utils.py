import tarfile
import zipfile
import gzip
import bz2
import re
import glob
import os
import logging
import shutil
import datetime

class Utils:
  '''
  Utility classes
  '''

  @staticmethod
  def month_to_num(date):
    return{
          'Jan' : 1,
          'Feb' : 2,
          'Mar' : 3,
          'Apr' : 4,
          'May' : 5,
          'Jun' : 6,
          'Jul' : 7,
          'Aug' : 8,
          'Sep' : 9,
          'Oct' : 10,
          'Nov' : 11,
          'Dec' : 12
          }[date]

  @staticmethod
  def copy_files(files_to_copy, to_dir, move=False):
    '''
    Copy or move files to to_dir, keeping directory structure.

    Copy keeps the original file stats.
    Files should have attributes name and root:
      - root: root directory
      - name: relative path of file in root directory

      /root/file/file1 will be copied in to_dir/file/file1

    :param files_to_copy: list of files to copy
    :type files_to_copy: list
    :param to_dir: destination directory
    :type to_dir: str
    :param move: move instead of copy
    :type move: bool
    '''
    nb_files = len(files_to_copy)
    cur_files = 1
    for file_to_copy in files_to_copy:
      logging.debug(str(cur_files)+'/'+str(nb_files)+' copy file '+file_to_copy['name'])
      cur_files += 1
      from_file = file_to_copy['root'] + '/' + file_to_copy['name']
      to_file = to_dir + '/' + file_to_copy['name']
      if not os.path.exists(os.path.dirname(to_file)):
        os.makedirs(os.path.dirname(to_file))
      if move:
        shutil.move(from_file, to_file)
      else:
        shutil.copyfile(from_file, to_file)
        shutil.copystat(from_file, to_file)

  @staticmethod
  def copy_files_with_regexp(from_dir, to_dir, regexps, move=False):
    '''
    Copy or move files from from_dir to to_dir matching regexps.
    Copy keeps the original file stats.

    :param from_dir: origin directory
    :type from_dir: str
    :param to_dir: destination directory
    :type to_dir: str
    :param regexps: list of regular expressions that files in from_dir should match to be copied
    :type regexps: list
    :param move: move instead of copy
    :type move: bool
    :return: list of copied files with their size
    '''
    #os.chdir(from_dir)
    files_to_copy = []
    for root, dirs, files in os.walk(from_dir, topdown=True):
      for name in files:
        for reg in regexps:
          file_relative_path = os.path.join(root, name).replace(from_dir,'')
          if file_relative_path.startswith('/'):
            file_relative_path = file_relative_path.replace('/', '', 1)
          if re.match(reg, file_relative_path):
            files_to_copy.append({'name': file_relative_path})
            continue

    for file_to_copy in files_to_copy:
      from_file = from_dir +'/' + file_to_copy['name']
      to_file = to_dir + '/' + file_to_copy['name']
      if not os.path.exists(os.path.dirname(to_file)):
        os.makedirs(os.path.dirname(to_file))
      if move:
        shutil.move(from_file, to_file)
      else:
        shutil.copyfile(from_file, to_file)
        shutil.copystat(from_file, to_file)
      file_to_copy['size'] = os.path.getsize(to_file)
      f_stat = datetime.datetime.fromtimestamp(os.path.getmtime(to_file))
      file_to_copy['year'] = str(f_stat.year)
      file_to_copy['month'] = str(f_stat.month)
      file_to_copy['day'] = str(f_stat.day)
    return files_to_copy

  @staticmethod
  def uncompress(file, remove=True):
    '''
    Test if file is an archive, and uncompress it
    Remove archive file if specified

    :param file: full path to file to check and uncompress
    :type file: str
    :param remove: remove archive if present
    :type remove: bool
    '''
    is_archive = False
    if tarfile.is_tarfile(file):
      logging.error('is tar')
      tfile = tarfile.TarFile(file)
      tfile.extractall(os.path.basename(file))
      tfile.close()
      is_archive = True
    elif zipfile.is_zipfile(file):
      zfile = zipfile.ZipFile(file)
      zfile.extractall(os.path.basename(file))
      zfile.close()
      is_archive = True
    elif file.endswith('.gz'):
      f_in = open(file.replace('.gz',''), 'wb')
      gz_file = gzip.GzipFile(file)
      f_in.writelines(gz_file.readlines())
      f_in.close()
      gz_file.close()
      is_archive = True
    elif file.endswith('.bz2'):
      f_in = open(file.replace('.bz2',''), 'wb')
      bz_file = bz2.BZ2File(file)
      f_in.writelines(bz_file.readlines())
      f_in.close()
      bz_file.close()
      is_archive = True

    if is_archive:
      logging.debug('Uncompress:uncompress:'+file)


    if is_archive and remove and os.path.exists(file):
      os.remove(file)
