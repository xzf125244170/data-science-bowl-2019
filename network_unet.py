import tensorflow as tf
from tensorflow.contrib import slim
from network_basic import NetworkBasic


class NetworkUnet(NetworkBasic):
    def __init__(self,
                 batchsize,
                 unet_weight,
                 batch_norm_decay=0.9,
                 batch_norm_epsilon=0.001,
                 keep_prob=0.9,
                 stddev=0.01,
                 ):
        super(NetworkUnet, self).__init__(batchsize=batchsize, unet_weight=unet_weight)
        self.batch_norm_decay = batch_norm_decay
        self.batch_norm_epsilon = batch_norm_epsilon
        self.keep_prob = keep_prob
        self.stddev = stddev

    @staticmethod
    def double_conv(net, nb_filter, scope, keep_prob):
        net = slim.convolution(net, nb_filter, [3, 3], 1, scope='%s_1' % scope)
        net = slim.dropout(net, keep_prob=keep_prob)
        net = slim.convolution(net, nb_filter, [3, 3], 1, scope='%s_2' % scope)
        return net

    def build(self):
        # https://github.com/tensorflow/tensorflow/blob/master/tensorflow/contrib/layers/python/layers/layers.py#L429
        batch_norm_params = {
            'is_training': self.is_training,
            'center': True,
            'scale': True,
            'decay': self.batch_norm_decay,
            'epsilon': self.batch_norm_epsilon,
            'fused': True,
            'zero_debias_moving_mean': True
        }

        dropout_params = {
            'keep_prob': self.keep_prob,
            'is_training': self.is_training,
        }

        conv_args = {
            'padding': 'SAME',
            'weights_initializer': tf.truncated_normal_initializer(mean=0.0, stddev=self.stddev),
            'normalizer_fn': slim.batch_norm,
            'normalizer_params': batch_norm_params,
            'activation_fn': tf.nn.elu
        }

        net = self.input_batch
        features = []

        with slim.arg_scope([slim.convolution, slim.conv2d_transpose], **conv_args):
            with slim.arg_scope([slim.dropout], **dropout_params):
                # down sampling steps
                for i in range(4):
                    net = NetworkUnet.double_conv(net,
                                                  int(32*(2**i)),
                                                  scope='down_conv_%d' % (i + 1),
                                                  keep_prob=self.keep_prob)
                    features.append(net)
                    net = slim.max_pool2d(net, [3, 3], 2, padding='SAME', scope='pool%d' % (i + 1))
                # middle
                net = NetworkUnet.double_conv(net, 512, scope='middle_conv_1', keep_prob=self.keep_prob)
                # upsampling steps
                for i in range(4):
                    net = slim.conv2d_transpose(net, int(256/(2**i)), [3, 3], 2, scope='up_trans_conv_%d' % (i + 1))
                    down_feat = features.pop()  # upsample with origin version
                    net = tf.concat([down_feat, net], axis=-1)
                    net = NetworkUnet.double_conv(net,
                                                  int(256/(2**i)),
                                                  scope='up_conv_%d' % (i + 1),
                                                  keep_prob=self.keep_prob)

                net = NetworkUnet.double_conv(net, 32, scope='output_conv_1', keep_prob=self.keep_prob)
        net = slim.convolution(net, 1, [3, 3], 1, scope='final_conv',
                               activation_fn=None,
                               padding='SAME',
                               weights_initializer=tf.truncated_normal_initializer(mean=0.0, stddev=self.stddev))

        self.logit = net
        self.output = tf.nn.sigmoid(net, 'visualization')
        if self.unet_weight:
            w = self.weight_batch
        else:
            w = 1.0

        self.loss = tf.losses.sigmoid_cross_entropy(
            multi_class_labels=self.mask_batch,
            logits=self.logit,
            weights=w
        )
        return net
