import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../models/trade.dart';
import 'config_provider.dart';

final tradeLogProvider = StreamProvider<List<Trade>>((ref) async* {
  final pathAsync = ref.watch(dataPathProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final root = pathAsync.valueOrNull;
  if (root == null) return;

  final file = File(p.join(root, 'state', 'trade_log.json'));
  while (true) {
    if (file.existsSync()) {
      try {
        final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        final trades = (json['trades'] as List<dynamic>)
            .map((t) => Trade.fromJson(t as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield trades;
      } on FormatException {
        // skip
      }
    } else {
      yield [];
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
