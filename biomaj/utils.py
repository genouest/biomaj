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
  def copy_files(from_dir, to_dir, regexps, move=False):
    #os.chdir(from_dir)
    files_to_copy = []
    for root, dirs, files in os.walk(from_dir, topdown=True):
      for name in files:
        for reg in regexps:
          file_relative_path = os.path.join(root, name).replace(from_dir,'')
          if re.match(reg, file_relative_path):
            files_to_copy.append(file_relative_path)
            continue

    for file_to_copy in files_to_copy:
      from_file = from_dir +'/' + file_to_copy
      to_file = to_dir + '/' + file_to_copy
      if not os.path.exists(os.path.dirname(to_file)):
        os.makedirs(os.path.dirname(to_file))
      if move:
        shutil.move(from_file, to_file)
      else:
        shutil.copyfile(from_file, to_file)
        shutil.copystat(from_file, to_file)

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
