import tarfile
import zipfile
import re
import glob
import os
import logging
import shutil

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
  def copy_files(from_dir, to_dir, regexps, move=False):
    #os.chdir(from_dir)
    files_to_copy = []
    for root, dirs, files in os.walk(from_dir, topdown=True):
      for name in files:
        for reg in regexps:
          file_relative_path = os.path.join(root, name).replace(from_dir,'')
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
    return files_to_copy

  @staticmethod
  def uncompress(file, remove=True):
    '''
    Test if file is an archive, and uncompress it
    Remove archive file if specified
    '''
    is_archive = False
    if tarfile.is_tarfile(file):
      tfile = tarfile.TarFile(file)
      tfile.extractall(os.path.basename(file))
      tfile.close()
      is_archive = True
    elif zipfile.is_zipfile(file):
      zfile = zipfile.ZipFile(file)
      zfile.extractall(os.path.basename(file))
      zfile.close()
      is_archive = True

    if is_archive and remove:
      os.remove(file)
