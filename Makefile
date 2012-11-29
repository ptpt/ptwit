pip:
	sudo pip install ptwit

setup:
	sudo python setup.py install

remove:
	sudo pip uninstall ptwit

upload:
	python setup.py sdist upload

clean:
	find . -name "*.pyc" -delete
	rm -f README.html
