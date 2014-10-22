import tarfile
import zipfile

class Utils:
  '''
  Utility classes
  '''

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
