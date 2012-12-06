setup:
	sudo python setup.py install

pip:
	sudo pip install ptwit

remove:
	sudo pip uninstall ptwit

upload:
	python setup.py sdist upload

clean:
	find . -name "*.pyc" -delete
	rm -f README.html
