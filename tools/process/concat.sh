# ! /bin/bash
# Script for Biomaj PostProcess
#
# concat files
#
# ARGS   :
#           1) regular expression for file to apply concat
#           2) regular expression for exclude files in result
#	    3) relativ path name (result of concat)
#           4) format (fasta)  [OPTIONAL]
#           5) types (type1,type2,...) [OPTIONAL]
#           6) tags  (key:value,key:value,...) [OPTIONAL]
#
#
#
# Default input from STDIN unless files specified. To explictly specify STDIN
# to be used for input use '-' as filename


if (test $# -lt 3) then
	echo "arguments:" 1>&2;
	echo "1: regular expression for include a set of file to apply concat" 1
>&2;
 	echo "2: regular expression for exclude a set of file to apply concat" 1
>&2;
 	echo "3: result file name (relative path from future_release and name)" 
1>&2;
 	exit -1;

fi

workdir=$datadir/$dirversion/$localrelease/
echo "apply concat with set $workdir/$1 to $workdir/$3";

#Creation des repertoires

dirtocreate=`dirname $workdir/$3`;

if (! test -e $dirtocreate ) then
	echo "mkdir :"$dirtocreate;
        mkdir -p $dirtocreate
fi

if ( test $? -ne 0 ) then
        echo "Cannot create $dirtocreate." 1>&2 ;
  	exit 1;
fi


cd $workdir;

echo ;

files='';

echo "set a list of file...";

for expr in $1
do
  #  echo "$expr";
  #  dir=`dirname $expr`;
  #  fileExp=`basename $expr`;
  if [ "$2" != "" ]
  then
    files="$files ""`echo $expr | egrep -v $2`";
  else
    files="$files $expr";
  fi
done

echo "";
echo "--------------------------";
echo "Comput [$workdir/$3]....";
echo "change directory:$workdir";
echo "$files > $workdir/$3";
rm -f $workdir/$3 2> /dev/null ;

if ( test -z "$files" )
then
    echo "Cannot create $workdir/$3 : no files !" 1>&2 ;
    exit 1;
fi

echo "cat $files > $workdir/$3";

for fileToConcat in $files
do
  cat $fileToConcat >> $workdir/$3 ;
        
  if ( test $? -ne 0 ) then
    echo "Cannot create $3.[error:$?]" 1>&2 ;
    exit 1;
  fi
done

format=""
types=""
tags=""
if [ "$4" != "" ]
then
  format=$4
fi
if [ "$5" != "" ]
then
  types=$5
fi
if [ "$6" != "" ]
then
  tags=$6
fi



echo "##BIOMAJ#$format#$types#$tags#$3"
