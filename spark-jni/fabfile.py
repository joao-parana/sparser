from __future__ import with_statement
from fabric.api import *

DATASETS_TO_BENCHMARK = ['tweets-trump.json', 'tweets23g.json', 'zakir16g.json']
GIT_PROMPT = {
    'Are you sure you want to continue connecting (yes/no)? ': 'yes',
}

@parallel
def clear_buffer_cache():
    run("free && sync && sudo sh -c 'echo 1 >/proc/sys/vm/drop_caches' && free")


@parallel
def move_file_to_ssd(filename):
    run('sudo mv %s /mnt/1/sparser/%s' % (filename, filename))


@parallel
def download_data(pool_size=3):
    for filename in DATASETS_TO_BENCHMARK:
        run('gsutil -m -o GSUtil:parallel_composite_upload_threshold=150M cp \
                gs://sparser/%s /mnt/1/%s' % (filename, filename))


@runs_once
def put_data_on_hdfs():
    for filename in DATASETS_TO_BENCHMARK:
        run('hadoop fs -put %s /user/fabuzaid21/%s' % (filename, filename))


@parallel
def build_sparser(code_dir):
    with cd('%s/spark-jni' % code_dir):
        run('git pull origin master')
        run('make clean && make')
    run('sudo ln -sfn %s/spark-jni/libsparser.so /usr/lib/libsparser.so' %
        code_dir)


@parallel
def get_sparser_code(code_dir):
    run('rm -rf sparser')
    with settings(prompts=GIT_PROMPT):
        run('git clone git@github.com:sppalkia/sparser.git %s' % code_dir)


def ls(path):
    run('ls -l %s' % path)


def push_ssh_key():
    run('mkdir -p ~/.ssh && chmod 700 ~/.ssh')
    # use private key generated by gcloud
    put('~/.ssh/google_compute_engine', '~/.ssh/id_rsa')
    run('chmod 700 ~/.ssh/id_rsa')


@parallel
def install_pivotal_libhdfs3(code_dir):
    run('rm -rf pivotalrd-libhdfs3')
    with settings(prompts=GIT_PROMPT):
        run('git clone https://github.com/Pivotal-Data-Attic/pivotalrd-libhdfs3.git'
            )
    with cd('pivotalrd-libhdfs3'):
        run('mkdir build')
        with cd('build'):
            run('../bootstrap --prefix=%s/common/libhdfs' % code_dir)
            run('make -j')
            run('make install')
    run('''sudo ln -sfn %s/common/libhdfs/lib/libhdfs3.so.1 \
            /usr/lib/libhdfs3.so.1''' % code_dir)


@parallel
def install_libs():
    with settings(prompts={'Do you want to continue? [Y/n] ': 'Y'}):
        run('sudo apt-get update')
        run('''sudo apt-get install -y protobuf-compiler \
               libprotobuf-dev libxml2-dev libkrb5-dev \
               libgsasl7-dev uuid-dev libboost-dev \
               clang-3.8 clang++-3.8 clang-format-3.8 \
               maven cmake tmux htop fabric''')
    run('sudo ln -sfn /usr/bin/clang++-3.8 /usr/bin/clang++')


@parallel
def install_config():
    with settings(prompts=GIT_PROMPT):
        run('git clone git@github.com:fabuzaid21/dotfiles.git')
        run('git clone git@github.com:fabuzaid21/Vim.git --branch vundle')
    with cd('dotfiles'):
        run('./install.sh')
    run('echo "export SPARK_HOME=/usr/lib/spark" >> ~/.bashrc.user')
    run('echo ". ~/.bashrc.user" >> ~/.bashrc')
    run('echo ". ~/.bashrc.user" >> ~/.bash_profile')


@parallel
def setup():
    code_dir = '/home/fabuzaid21/sparser'
    run('sudo mkdir -p /mnt/1/sparser')
    push_ssh_key()
    install_libs()
    install_config()
    get_sparser_code(code_dir)
    install_pivotal_libhdfs3(code_dir)
    build_sparser(code_dir)
    download_data()
