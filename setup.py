# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


# long_description = open('README.rst').read()


setup(
    name='django-service-interactor',
    version='0.0.1',
    description='',
    # long_description=long_description,
    author='IARP OpenSource',
    author_email='iarp.opensource@gmail.com',
    url='https://github.com/iarp/django-service-interactor',
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    zip_safe=False,
    install_requires=[
        'django',
        'django-allauth',
        'python-dateutil',
        'pytz',
    ],
)
