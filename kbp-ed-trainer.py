#!/eecs/research/asr/mingbin/python-workspace/hopeless/bin/python

"""
Author      : Mingbin Xu (mingbin.xu@gmail.com)
Filename    : kbp-ed-trainer.py
Last Update : Jul 26, 2016
Description : N/A
Website     : https://wiki.eecs.yorku.ca/lab/MLL/

Copyright (c) 2016 iNCML (author: Mingbin Xu)
License: MIT License (see ../LICENSE)
"""

import argparse, logging, time, cPickle
from itertools import product, chain


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument( 'word_embedding', type = str, 
                         help = 'word_embedding.{-case-insensitive, -case-sensitive}.word2vec are assumed'  )
    parser.add_argument( 'data_path', type = str, 
                         help = 'path to ed-eng-{train,eval} of KBP2015' )

    # training-related arguments
    parser.add_argument( '--n_char_embedding', type = int, default = 32,
                         help = 'char embedding dimension' )
    parser.add_argument( '--n_ner_embedding', type = int, default = 32,
                         help = 'ner embedding dimension' )
    parser.add_argument( '--n_char', type = int, default = 128,
                         help = 'character set size. since ascii is used; 128 is assumed' )
    parser.add_argument( '--layer_size', type = str, default = '512,512,512',
                         help = 'size of fully connected layers after projection' )
    parser.add_argument( '--n_batch_size', type = int, default = 512,
                         help = 'mini batch size; the last one may be smaller' )
    parser.add_argument( '--learning_rate', type = float, default = 0.1024,
                         help = 'global initial learning rate' )
    parser.add_argument( '--momentum', type = float, default = 0.9,
                         help = 'momentum value when MomentumOptimizer is used' )
    parser.add_argument( '--max_iter', type = int, default = 64,
                         help = 'maximum number of iterations' )
    parser.add_argument( '--feature_choice', type = int, default = 767,
                         help = 'the features used are pick with a bit mask. They are ' + 
                                '1) case-insensitive/character-level bfofe with candidate word(s), ' +
                                '2) case-insensitive/character-level bfofe without candidate word(s), ' + 
                                '3) case-insensitive/character-level bag-of-words, ' + 
                                '4) case-sensitive/word-level bfofe with candidate word(s), ' +
                                '5) case-sensitive/word-level bfofe without candidate word(s), ' + 
                                '6) case-sensitive/word-level bag-of-words, ' + 
                                '7) char-level bfofe of candidate word(s), ' + 
                                '8) char-level bfofe of candidate initial, ' + 
                                '9) gazetteer exact match, ' +
                                '10) character-convolution'
                                'e.g. if choice is 0b000111111, feature 1 to 6 are used' )
    parser.add_argument( '--overlap_rate', type = float, default = 0.08,
                         help = 'what percentage of overlap examples is used during training' )
    parser.add_argument( '--disjoint_rate', type = float, default = 0.016,
                         help = 'what percentage of disjoint example is used during training' )
    parser.add_argument( '--dropout', action = 'store_true', default = False,
                         help = 'whether to use dropout or not' )
    parser.add_argument( '--char_alpha', type = float, default = 0.8,
                         help = 'char-level forgetting factor' )
    parser.add_argument( '--word_alpha', type = float, default = 0.5,
                         help = 'word-level forgetting factor' )
    parser.add_argument( '--share_word_embedding', action = 'store_true', default = False,
                         help = 'whether or not bow and context share a same word embedding' )
    parser.add_argument( '--n_window', type = int, default = 7,
                         help = 'maximum length of NER candidate' )
    parser.add_argument( '--strictly_one_hot', action = 'store_true', default = False,
                         help = 'when gazetteer is used, True if 7-bit match or False 5-bit match' )
    parser.add_argument( '--hope_out', type = int, default = 0,
                         help = 'dimension of z in the HOPE paper; 0 means not used' )
    parser.add_argument( '--n_label_type', type = int, default = 10,
                         help = 'By default, PER, LOC, ORG and MISC are assumed' )
    parser.add_argument( '--kernel_height', type = str, default = '2,3,4,5,6,7,8,9' )
    parser.add_argument( '--kernel_depth', type = str, default = ','.join( ['16'] * 8 ) )
    parser.add_argument( '--enable_distant_supervision', action = 'store_true', default = False ) 
    parser.add_argument( '--initialize_method', type = str, default = 'uniform',
                         choices = [ 'uniform', 'gaussian' ] )
    parser.add_argument( '--model', type = str, default = 'kbp2016' )
    parser.add_argument( '--iflytek', action = 'store_true', default = False )
    parser.add_argument( '--language', type = str, choices = ['eng', 'cmn', 'spa'], default = 'eng' )
    parser.add_argument( '--average', action = 'store_true', default = False,
                         help = 'word embedding is averaged on number of characters ' + \
                                'when word level feature is used in Chinese' )
    parser.add_argument( '--buffer_dir', type = str, default = './' )

    # experimental
    parser.add_argument( '--is_2nd_pass', action = 'store_true', default = False,
                         help = 'run 2nd pass training when true' )
    parser.add_argument( '--skip_test', action = 'store_true', default = False,
                         help = 'skip test set when set' )
    parser.add_argument( '--logfile', type = str, default = None )
    parser.add_argument( '--optimizer', type = str, default = 'momentum', choices = ['momentum', 'adam'] )
    parser.add_argument( '--version', type = int, default = 1, choices = [1, 2, 3],
                         help = 'version consumes less memory' )

    ########################################################################

    args = parser.parse_args()

    ########################################################################

    # set a logging file at DEBUG level, TODO: windows doesn't allow ":" appear in a file name
    if args.logfile is None:
        logfile = ('log/kbp ' + time.ctime() + '.log').replace(' ', '-')
    else:
        logfile = args.logfile

    logging.basicConfig( 
        format = '%(asctime)s : %(levelname)s : %(message)s', 
        level= logging.DEBUG,
        filename = logfile, 
        filemode = 'w' 
    )

    # direct the INFO-level logging to the screen
    console = logging.StreamHandler()
    console.setLevel( logging.INFO )
    console.setFormatter( logging.Formatter( '%(asctime)s : %(levelname)s : %(message)s' ) )
    logging.getLogger().addHandler( console )

    logger = logging.getLogger()

    ########################################################################

    logger.info( str(args) + '\n' )

    ########################################################################

    if args.is_2nd_pass:
        logger.info( 'user-input feature-choice was %d' % args.feature_choice )
        args.feature_choice &= 2038
        logger.info( 'feature-choice now is %d' % args.feature_choice )

    if args.language == 'cmn':
        logger.info( 'user-input feature-choice was %d' % args.feature_choice )
        args.feature_choice &= 895
        logger.info( 'feature-choice now is %d' % args.feature_choice )

    ########################################################################

    from fofe_mention_net import *
    config = mention_config( args )

    ########################################################################

    if args.version == 2:
        mention_net = fofe_mention_net_v2( config )
    elif args.version == 3:
        import torch.optim.lr_scheduler as lr_scheduler
        mention_net = fofe_mention_net_v3( config )
        scheduler = lr_scheduler.ReduceLROnPlateau(
            mention_net.optimizer,
            mode = 'min',
            factor = 0.5,
            patience = 16,
            min_lr = 0.001
        )
    else:
        mention_net = fofe_mention_net( config )
    mention_net.tofile( args.model )

    ########################################################################

    # there are 2 sets of vocabulary, case-insensitive and case sensitive
    nt = config.n_label_type if config.is_2nd_pass else 0
    if config.language != 'cmn':
        numericizer1 = vocabulary( 
            config.word_embedding + '-case-insensitive.wordlist', 
            config.char_alpha, 
            False,
            n_label_type = nt 
        )
        numericizer2 = vocabulary( 
            config.word_embedding + '-case-sensitive.wordlist', 
            config.char_alpha, 
            True,
            n_label_type = nt 
        )
    else:
        numericizer1 = chinese_word_vocab( 
            config.word_embedding + '-char.wordlist',
            n_label_type = nt,
        )
        numericizer2 = chinese_word_vocab( 
            config.word_embedding + \
                ('-avg.wordlist' if config.average else '-word.wordlist'),
            n_label_type = nt
        )
        numericizer1.loadWubiKeyStroke( config.word_embedding + '.wubi' )
    

    try:
        logger.info( 'Loading compressed gazetteer' )
        pkl_path = os.path.join( config.data_path, 'kbp-gaz.pkl' )
        with open( pkl_path, 'rb' ) as fp:
            kbp_gazetteer = cPickle.load( fp )
    except:
        logger.info( 'loading text gazetteer' )
        txt_path = os.path.join( config.data_path, 'kbp-gaz.txt' )
        kbp_gazetteer = gazetteer( txt_path, mode = 'KBP' )

    source = imap( 
        lambda x: x[:4],
        LoadED( config.data_path + '/%s-train-parsed' % config.language ) 
    ) 

    if args.iflytek:
        source = chain( 
            source,
            imap( lambda x: x[:4], 
                  LoadED( 'iflytek-clean-%s' % config.language ) 
            ) 
        )

    if args.version > 1:
        human = batch_constructor_v2( 
            source,
            numericizer1, 
            numericizer2, 
            gazetteer = kbp_gazetteer,  
            window = config.n_window, 
            n_label_type = config.n_label_type,
            language = config.language,
            is_2nd_pass = args.is_2nd_pass 
        )
    else:
        human = batch_constructor( 
            source,
            numericizer1, 
            numericizer2, 
            gazetteer = kbp_gazetteer, 
            alpha = config.word_alpha, 
            window = config.n_window, 
            n_label_type = config.n_label_type,
            language = config.language,
            is2ndPass = args.is_2nd_pass 
        )
    logger.info( 'human: ' + str(human) )
    
    if args.version > 1:
        valid = batch_constructor_v2( 
            imap( lambda x: x[:4], 
                  LoadED( config.data_path + '/%s-eval-parsed' % config.language ) 
            ), 
            numericizer1, 
            numericizer2, 
            gazetteer = kbp_gazetteer, 
            window = config.n_window, 
            n_label_type = config.n_label_type,
            language = config.language,
            is_2nd_pass = args.is_2nd_pass 
        )
    else:
        valid = batch_constructor( 
            imap( lambda x: x[:4], 
                  LoadED( config.data_path + '/%s-eval-parsed' % config.language ) 
            ), 
            numericizer1, 
            numericizer2, 
            gazetteer = kbp_gazetteer, 
            alpha = config.word_alpha, 
            window = config.n_window, 
            n_label_type = config.n_label_type,
            language = config.language,
            is2ndPass = args.is_2nd_pass 
        )
    logger.info( 'valid: ' + str(valid) )
    
    # test = batch_constructor( 
    #     imap( lambda x: x[:4], 
    #           LoadED( config.data_path + '/%s-train-parsed' % config.language ) 
    #     ),
    #     numericizer1, 
    #     numericizer2, 
    #     gazetteer = kbp_gazetteer, 
    #     alpha = config.word_alpha, 
    #     window = config.n_window, 
    #     n_label_type = config.n_label_type,
    #     language = config.language,
    #     is2ndPass = args.is_2nd_pass 
    # )
    test = human
    logger.info( 'test: ' + str(test) )

    logger.info( 'data set loaded' )


    ################### let's compute ####################

    prev_cost, decay_started = 2054, False

    infinite_human = human.infinite_mini_batch_multi_thread( 
        config.n_batch_size, 
        True, 
        config.overlap_rate, 
        config.disjoint_rate, 
        config.feature_choice, 
        True 
    )

    if args.version > 1:
        target = lambda x : x['target']
    else:
        target = lambda x : x[-1]

    for n_epoch in xrange( config.max_iter ):

        valid_predicted_file = os.path.join(
            args.buffer_dir, 'kbp-valid.predicted'
        )

        test_predicted_file = os.path.join(
            args.buffer_dir, 'kbp-test.predicted'
        )

        valid_predicted = open( valid_predicted_file, 'wb' )

        if not args.skip_test:
            test_predicted = open( test_predicted_file, 'wb' )

        #############################################
        ########## go through training set ##########
        #############################################

        if config.enable_distant_supervision:
            X, Y = n_epoch / 16, n_epoch % (16 if not args.iflytek else 4)
            dsp = distant_supervision_parser( 
                    'distant-supervision/data-chunk/sentence-%02d' % X,
                    'distant-supervision/data-chunk/labels-%02d' % X,
                    Y, None, 64 if not args.iflytek else 16  )
            train = batch_constructor( 
                dsp, 
                numericizer1, 
                numericizer2, 
                gazetteer = kbp_gazetteer, 
                alpha = config.word_alpha, 
                window = config.n_window, 
                n_label_type = config.n_label_type,
                language = config.language 
            )
            logger.info( 'train: ' + str(train) )
        else:
            train = human

        # phar is used to observe training progress
        logger.info( 'epoch %2d, learning-rate: %f' % \
                        (n_epoch + 1, mention_net.config.learning_rate) )
        total = len(train.positive) + \
                int(len(train.overlap) * config.overlap_rate) + \
                int(len(train.disjoint) * config.disjoint_rate)
        pbar = tqdm( total = total )

        cost, cnt = 0, 0
            
        for x in ifilter(
            lambda x : len(target(x)) == config.n_batch_size,
            train.mini_batch_multi_thread( 
                config.n_batch_size, 
                True, 
                config.overlap_rate, 
                config.disjoint_rate, 
                config.feature_choice 
            ) 
        ):
            if config.enable_distant_supervision:
                x = [ x, infinite_human.next() ]
                if choice( [ True, False ] ):
                    x.append( infinite_human.next() )
            else:
                x = [ x ]

            for example in x:
                c = mention_net.train( example )

                cost += c * len(target(example))
                cnt += len(target(example))
            pbar.update( len(target(example)) )

        pbar.close()
        train_cost = cost / cnt 
        logger.info( 'training set iterated, %f' % train_cost )

        ########################################################################

        if n_epoch + 1 == config.max_iter:
        # if config.enable_distant_supervision or \
        #     n_epoch + 1 == config.max_iter or \
        #     (n_epoch + 1) % min(16, config.max_iter / 16) == 0:
            ###############################################
            ########## go through validation set ##########
            ###############################################

            cost, cnt = 0, 0
            for example in valid.mini_batch_multi_thread( 
                            256 if config.feature_choice & (1 << 9 ) > 0 else 1024, 
                            False, 1, 1, config.feature_choice ):

                c, pi, pv = mention_net.eval( example )

                cost += c * len(target(example))
                cnt += len(target(example))
                for expected, estimate, probability in zip( target(example), pi, pv ):
                    print >> valid_predicted, '%d  %d  %s' % \
                            (expected, estimate, '  '.join( [('%f' % x) for x in probability.tolist()] ))

            valid_cost = cost / cnt 
            valid_predicted.close()

            #########################################
            ########## go through test set ##########
            #########################################

            if not args.skip_test:
                cost, cnt = 0, 0
                for example in test.mini_batch_multi_thread( 
                                256 if config.feature_choice & (1 << 9 ) > 0 else 1024, 
                                False, 1, 1, config.feature_choice ):

                    c, pi, pv = mention_net.eval( example )

                    cost += c * len(target(example))
                    cnt += len(target(example))
                    for expected, estimate, probability in zip( target(example), pi, pv ):
                        print >> test_predicted, '%d  %d  %s' % \
                                (expected, estimate, '  '.join( [('%f' % x) for x in probability.tolist()] ))

                test_cost = cost / cnt 
                test_predicted.close()

            ###################################################################################
            ########## exhaustively iterate 3 decodding algrithms with 0.x cut-off ############
            ###################################################################################

            # logger.info( 'cost: %f (train), %f (valid), %f (test)', train_cost, valid_cost, test_cost )
            if args.skip_test:
                logger.info( 'cost: %f (train), %f (valid)', train_cost, valid_cost )
            else:
                logger.info( 'cost: %f (train), %f (valid), %f (test)', train_cost, valid_cost, test_cost )

            # algo_list = ['highest-first', 'longest-first', 'subsumption-removal']
            idx2algo = { 1: 'highest-first', 2: 'longest-first', 3:'subsumption-removal'  }
            algo2idx = { 'highest-first': 1, 'longest-first': 2, 'subsumption-removal': 3 }

            best_dev_fb1, best_threshold, best_algorithm = 0, [0.5, 0.5], [1, 1]

            if n_epoch >= config.max_iter / 2:
                pp = [ p for p in PredictionParser( # KBP2015(  data_path + '/ed-eng-eval' ), 
                    imap( lambda x: x[:4], LoadED( config.data_path + '/%s-eval-parsed' % config.language ) ),
                    valid_predicted_file, 
                    config.n_window,
                    n_label_type = config.n_label_type 
                ) ]

                for algorithm in product( [1, 2], repeat = 2 ):
                    algorithm = list( algorithm )
                    name = [ idx2algo[i] for i in algorithm  ]
                    for threshold in product( [ 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9 ], repeat = 2 ):
                        threshold = list( threshold )

                        precision, recall, f1, _ = evaluation( pp, threshold, algorithm, True,
                                                               n_label_type = config.n_label_type )
                        # logger.debug( ('cut-off: %f, algorithm: %-20s' % (threshold, name)) + 
                        #               (', validation -- precision: %f,  recall: %f,  fb1: %f' % (precision, recall, f1)) )
                        if f1 > best_dev_fb1:
                            best_dev_fb1, best_threshold, best_algorithm = f1, threshold, algorithm
                            best_precision, best_recall = precision, recall
                            mention_net.config.algorithm = best_algorithm
                            mention_net.config.threshold = best_threshold
                            mention_net.tofile( args.model )

            logger.info( 'cut-off: %s, algorithm: %-20s' % \
                         (str(best_threshold), str([ idx2algo[i] for i in best_algorithm ])) )

            precision, recall, f1, info = evaluation( 
                PredictionParser( 
                    imap( lambda x: x[:4], LoadED( config.data_path + '/%s-eval-parsed' % config.language ) ),
                    valid_predicted_file, 
                    config.n_window,
                    n_label_type = config.n_label_type 
                ), 
                best_threshold, 
                best_algorithm, 
                True,
                analysis = None, #analysis,
                n_label_type = config.n_label_type 
            )
            logger.info( '%s\n%s' % ('validation', info) ) 

            if not args.skip_test:
                precision, recall, f1, info = evaluation( 
                    PredictionParser( # KBP2015(  data_path + '/ed-eng-train' ),
                        imap( lambda x: x[:4], LoadED( config.data_path + '/%s-train-parsed' % config.language ) ),
                        test_predicted_file, 
                        config.n_window,
                        n_label_type = config.n_label_type 
                    ), 
                    best_threshold, 
                    best_algorithm, 
                    True,
                    analysis = None, #analysis,
                    n_label_type = config.n_label_type 
                )
                logger.info( '%s\n%s' % ('test', info) ) 

        if args.version == 3:
            scheduler.step( train_cost )
        else:
            mention_net.config.learning_rate *= 0.5 ** ((4./ config.max_iter) if config.drop_rate > 0 else (1./ 2))
        mention_net.config.drop_rate *= 0.5 ** (2./ config.max_iter)

    logger.info( 'results are written in kbp-result/kbp-{valid,test}.predicted' )
