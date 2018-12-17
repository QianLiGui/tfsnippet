import pytest
import tensorflow as tf

from tfsnippet.utils import global_reuse, VarScopeObject, instance_reuse


def _make_var_and_op():
    vs = tf.get_variable_scope()
    var = tf.get_variable('var', shape=(), dtype=tf.float32)
    op = tf.add(1, 2, name='op')
    return vs, var, op


def _make_variable_scope():
    vs = tf.get_variable_scope()
    var = tf.get_variable('var', shape=(), dtype=tf.float32)
    return vs, var


def _make_variable_scopes():
    with tf.variable_scope(None, default_name='vs') as vs1:
        var1 = tf.get_variable('var', shape=(), dtype=tf.float32)
    with tf.variable_scope(None, default_name='vs') as vs2:
        var2 = tf.get_variable('var', shape=(), dtype=tf.float32)
    return (vs1, var1), (vs2, var2)


class InstanceReuseTestCase(tf.test.TestCase):

    def test_errors(self):
        class _Reusable(object):
            def __init__(self):
                self.variable_scope = ''

            @instance_reuse('foo')
            def f(self):
                pass

        obj = _Reusable()
        with pytest.raises(TypeError, match='`variable_scope` attribute of '
                                            'the instance .* is expected to '
                                            'be a `tf.VariableScope`.*'):
            obj.f()

        with pytest.raises(TypeError, match='`method` seems not to be an '
                                            'instance method.*'):
            @instance_reuse('foo')
            def f():
                pass

        with pytest.raises(TypeError, match='`method` seems not to be an '
                                            'instance method.*'):
            @instance_reuse('foo')
            def f(a):
                pass

        with pytest.raises(TypeError, match='`method` is expected to be '
                                            'unbound instance method'):
            obj = _Reusable()
            instance_reuse(obj.f)

    def test_nested_name_should_cause_an_error(self):
        with pytest.raises(ValueError, match='`global_reuse` does not support '
                                             '"/" in scope name'):
            @global_reuse('nested/scope')
            def nested_scope():
                return tf.get_variable('var', shape=(), dtype=tf.float32)

    def test_create_in_root_scope(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse('foo')
            def foo(self):
                return _make_var_and_op()

        with tf.Graph().as_default():
            o = MyScopeObject('o')

            # test enter for the first time
            vs, var, op = o.foo()
            self.assertEqual(vs.name, 'o/foo')
            self.assertEqual(var.name, 'o/foo/var:0')
            # YES! THIS IS THE EXPECTED BEHAVIOR!
            self.assertEqual(op.name, 'foo/op:0')

            # test enter for the second time
            vs, var, op = o.foo()
            self.assertEqual(vs.name, 'o/foo')
            self.assertEqual(var.name, 'o/foo/var:0')
            self.assertEqual(op.name, 'foo_1/op:0')

            # now we enter a variable scope, and then call `foo` twice.
            with tf.variable_scope('parent'):
                # call the method for the first time
                vs, var, op = o.foo()
                self.assertEqual(vs.name, 'o/foo')
                self.assertEqual(var.name, 'o/foo/var:0')
                self.assertEqual(op.name, 'parent/foo/op:0')

                # call the method for the second time
                vs, var, op = o.foo()
                self.assertEqual(vs.name, 'o/foo')
                self.assertEqual(var.name, 'o/foo/var:0')
                self.assertEqual(op.name, 'parent/foo_1/op:0')

    def test_create_in_parent_scope(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse('foo')
            def foo(self):
                return _make_var_and_op()

        with tf.Graph().as_default():
            with tf.variable_scope('parent'):
                o = MyScopeObject('o')

            # test enter for the first time
            vs, var, op = o.foo()
            self.assertEqual(vs.name, 'parent/o/foo')
            self.assertEqual(var.name, 'parent/o/foo/var:0')
            # YES! THIS IS THE EXPECTED BEHAVIOR!
            self.assertEqual(op.name, 'foo/op:0')

            # test enter for the second time
            vs, var, op = o.foo()
            self.assertEqual(vs.name, 'parent/o/foo')
            self.assertEqual(var.name, 'parent/o/foo/var:0')
            self.assertEqual(op.name, 'foo_1/op:0')

            # now we enter a variable scope, and then call `foo` twice.
            with tf.variable_scope('another'):
                # call the method for the first time
                vs, var, op = o.foo()
                self.assertEqual(vs.name, 'parent/o/foo')
                self.assertEqual(var.name, 'parent/o/foo/var:0')
                self.assertEqual(op.name, 'another/foo/op:0')

                # call the method for the second time
                vs, var, op = o.foo()
                self.assertEqual(vs.name, 'parent/o/foo')
                self.assertEqual(var.name, 'parent/o/foo/var:0')
                self.assertEqual(op.name, 'another/foo_1/op:0')

    def test_call_in_original_name_scope(self):
        class MyScopeObject(VarScopeObject):
            def _variable_scope_created(self, vs):
                self.vs, self.var, self.op = self.foo()

            @instance_reuse('foo')
            def foo(self):
                return _make_var_and_op()

        with tf.Graph().as_default():
            o = MyScopeObject('o')

            # call within _variable_scope_created should not generate
            # a new name scope.
            self.assertEqual(o.vs.name, 'o/foo')
            self.assertEqual(o.var.name, 'o/foo/var:0')
            self.assertEqual(o.op.name, 'o/foo/op:0')

            # call it for the second time within the object's variable scope
            # and the object's original name scope (this actually will not
            # happen in a regular program).
            with tf.variable_scope(o.variable_scope,
                                   auxiliary_name_scope=False):
                with tf.name_scope(o.variable_scope.original_name_scope):
                    vs, var, op = o.foo()
                    self.assertEqual(vs.name, 'o/foo')
                    self.assertEqual(var.name, 'o/foo/var:0')
                    self.assertEqual(op.name, 'o/foo_1/op:0')

    def test_create_variable_scopes_with_default_name(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse('foo')
            def foo(self):
                return _make_variable_scopes()

        with tf.Graph().as_default():
            o = MyScopeObject('o')

            # test enter for the first time
            (vs1, var1), (vs2, var2) = o.foo()
            self.assertEqual(vs1.name, 'o/foo/vs')
            self.assertEqual(var1.name, 'o/foo/vs/var:0')
            self.assertEqual(vs2.name, 'o/foo/vs_1')
            self.assertEqual(var2.name, 'o/foo/vs_1/var:0')

            # test enter for the second time, should reuse the variables
            (vs1, var1), (vs2, var2) = o.foo()
            self.assertEqual(vs1.name, 'o/foo/vs')
            self.assertEqual(var1.name, 'o/foo/vs/var:0')
            self.assertEqual(vs2.name, 'o/foo/vs_1')
            self.assertEqual(var2.name, 'o/foo/vs_1/var:0')

    def test_auto_choose_scope_name(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse
            def foo(self):
                return _make_variable_scope()

        with tf.Graph().as_default():
            o = MyScopeObject('o')
            vs, var = o.foo()
            self.assertEqual(vs.name, 'o/foo')
            self.assertEqual(var.name, 'o/foo/var:0')

    def test_uniquified_scope_name(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse('foo')
            def f1(self):
                return _make_variable_scope()

            @instance_reuse('foo')
            def f2(self):
                return _make_variable_scope()

        with tf.Graph().as_default():
            o = MyScopeObject('o')

            # first call to f1
            vs1, var1 = o.f1()
            self.assertEqual(vs1.name, 'o/foo')
            self.assertEqual(var1.name, 'o/foo/var:0')

            # this function should have a different variable scope than
            # the previous function.
            vs2, var2 = o.f2()
            self.assertEqual(vs2.name, 'o/foo_1')
            self.assertEqual(var2.name, 'o/foo_1/var:0')

    def test_two_instances(self):
        class MyScopeObject(VarScopeObject):
            @instance_reuse
            def foo(self):
                return _make_variable_scope()

        with tf.Graph().as_default():
            o1 = MyScopeObject('o1')
            vs1, var1 = o1.foo()
            self.assertEqual(vs1.name, 'o1/foo')
            self.assertEqual(var1.name, 'o1/foo/var:0')

            o2 = MyScopeObject('o2')
            vs2, var2 = o2.foo()
            self.assertEqual(vs2.name, 'o2/foo')
            self.assertEqual(var2.name, 'o2/foo/var:0')


class GlobalReuseTestCase(tf.test.TestCase):

    def test_nested_name_should_cause_an_error(self):
        with pytest.raises(ValueError, match='`global_reuse` does not support '
                                             '"/" in scope name'):
            @global_reuse('nested/scope')
            def nested_scope():
                return tf.get_variable('var', shape=(), dtype=tf.float32)

    def test_create_in_root_scope(self):
        @global_reuse('the_scope')
        def make_var_and_op():
            return _make_var_and_op()

        with tf.Graph().as_default():
            # test enter for the first time
            vs, var, op = make_var_and_op()
            self.assertEqual(vs.name, 'the_scope')
            self.assertEqual(var.name, 'the_scope/var:0')
            self.assertEqual(op.name, 'the_scope/op:0')

            # enter for the second time
            vs, var, op = make_var_and_op()
            self.assertEqual(vs.name, 'the_scope')
            self.assertEqual(var.name, 'the_scope/var:0')
            self.assertEqual(op.name, 'the_scope_1/op:0')

            # now we enter a variable scope, and then call the method twice.
            with tf.variable_scope('parent'):
                # call the method for the first time
                vs, var, op = make_var_and_op()
                self.assertEqual(vs.name, 'the_scope')
                self.assertEqual(var.name, 'the_scope/var:0')
                self.assertEqual(op.name, 'parent/the_scope/op:0')

                # call the method for the second time
                vs, var, op = make_var_and_op()
                self.assertEqual(vs.name, 'the_scope')
                self.assertEqual(var.name, 'the_scope/var:0')
                self.assertEqual(op.name, 'parent/the_scope_1/op:0')

    def test_create_in_parent_scope(self):
        @global_reuse('the_scope')
        def make_var_and_op():
            return _make_var_and_op()

        with tf.Graph().as_default():
            # open the parent scope
            with tf.variable_scope('parent'):
                # test enter for the first time
                vs, var, op = make_var_and_op()
                self.assertEqual(vs.name, 'the_scope')
                self.assertEqual(var.name, 'the_scope/var:0')
                self.assertEqual(op.name, 'parent/the_scope/op:0')

                # enter for the second time
                vs, var, op = make_var_and_op()
                self.assertEqual(vs.name, 'the_scope')
                self.assertEqual(var.name, 'the_scope/var:0')
                self.assertEqual(op.name, 'parent/the_scope_1/op:0')

            # now we reach the root scope, and then call the method twice.
            # call the method for the first time
            vs, var, op = make_var_and_op()
            self.assertEqual(vs.name, 'the_scope')
            self.assertEqual(var.name, 'the_scope/var:0')
            self.assertEqual(op.name, 'the_scope_1/op:0')

            # call the method for the second time
            vs, var, op = make_var_and_op()
            self.assertEqual(vs.name, 'the_scope')
            self.assertEqual(var.name, 'the_scope/var:0')
            self.assertEqual(op.name, 'the_scope_2/op:0')

    def test_create_variable_scopes_with_default_name(self):
        @global_reuse('the_scope')
        def make_variable_scopes():
            return _make_variable_scopes()

        with tf.Graph().as_default():
            # test enter for the first time
            (vs1, var1), (vs2, var2) = make_variable_scopes()
            self.assertEqual(vs1.name, 'the_scope/vs')
            self.assertEqual(var1.name, 'the_scope/vs/var:0')
            self.assertEqual(vs2.name, 'the_scope/vs_1')
            self.assertEqual(var2.name, 'the_scope/vs_1/var:0')

            # test enter for the second time, should reuse the variables
            (vs1, var1), (vs2, var2) = make_variable_scopes()
            self.assertEqual(vs1.name, 'the_scope/vs')
            self.assertEqual(var1.name, 'the_scope/vs/var:0')
            self.assertEqual(vs2.name, 'the_scope/vs_1')
            self.assertEqual(var2.name, 'the_scope/vs_1/var:0')

    def test_auto_choose_scope_name(self):
        @global_reuse
        def f():
            return _make_variable_scope()

        with tf.Graph().as_default():
            vs, var = f()
            self.assertEqual(vs.name, 'f')
            self.assertEqual(var.name, 'f/var:0')

    def test_uniquified_scope_name(self):
        @global_reuse('the_scope')
        def f1():
            return _make_variable_scope()

        @global_reuse('the_scope')
        def f2():
            return _make_variable_scope()

        with tf.Graph().as_default():
            vs1, var1 = f1()
            self.assertEqual(vs1.name, 'the_scope')
            self.assertEqual(var1.name, 'the_scope/var:0')

            # this function should have a different variable scope than
            # the previous function.
            vs2, var2 = f2()
            self.assertEqual(vs2.name, 'the_scope_1')
            self.assertEqual(var2.name, 'the_scope_1/var:0')

    def test_different_graph(self):
        @global_reuse('the_scope')
        def f():
            return _make_variable_scope()

        with tf.Graph().as_default() as graph1:
            vs, var1 = f()
            self.assertEqual(vs.name, 'the_scope')
            self.assertIs(var1.graph, graph1)
            self.assertEqual(var1.name, 'the_scope/var:0')

        with graph1.as_default():
            vs, var1_1 = f()
            self.assertEqual(vs.name, 'the_scope')
            self.assertIs(var1_1, var1)

        with tf.Graph().as_default() as graph2:
            vs, var2 = f()
            self.assertEqual(vs.name, 'the_scope')
            self.assertIs(var2.graph, graph2)
            self.assertEqual(var2.name, 'the_scope/var:0')
