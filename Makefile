.PHONY: setup pip remove upload clean

setup:
	python setup.py install

pip:
	pip install ptwit

remove:
	pip uninstall ptwit

upload:
	python setup.py sdist upload

clean:
	sudo rm -r build/ dist/ ptwit.egg-info/
	find . -name "*.pyc" -delete
	rm -f README.html
