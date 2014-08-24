﻿from benchmark import *


class octane(Benchmark):
    CONFIG = {
        'name': 'Octane',
        'metric': 'score',
        'path': {
            '2.0': {
                'external': 'http://octane-benchmark.googlecode.com/svn/latest/index.html',
                'internal': 'webbench/octane/2.0/index.html',
            },
            '1.0': {
                'external': 'http://octane-benchmark.googlecode.com/svn/tags/v1/index.html',
                'internal': 'browsermark',
            }
        },
        'version': '2.0',
    }

    def __init__(self, driver, case):
        super(octane, self).__init__(driver, case)

    def cond0(self, driver):
        self.e = driver.find_element_by_id('run-octane')
        if self.e:
            return True
        else:
            return False

    def act0(self, driver):
        self.e.click()

    def cond1(self, driver):
        self.e = driver.find_element_by_id('main-banner')
        if self.e.text.find('Score:') != -1:
            return True
        else:
            return False

    def act1(self, driver):
        pass

    states = [
        [cond0, act0],
        [cond1, None],
    ]

    def get_result(self, driver):
        results = []
        pattern = re.compile('Octane Score: (\d+)')
        match = pattern.search(self.e.text)
        results.append(match.group(1))

        subs = driver.find_elements_by_class_name('p-result')
        for sub in subs:
            results.append(sub.get_attribute('innerText'))
        return results