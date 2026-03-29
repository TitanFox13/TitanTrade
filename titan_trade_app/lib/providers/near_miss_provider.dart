import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../models/near_miss.dart';
import 'config_provider.dart';

final nearMissProvider = StreamProvider<List<NearMiss>>((ref) async* {
  final pathAsync = ref.watch(dataPathProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final root = pathAsync.valueOrNull;
  if (root == null) return;

  final file = File(p.join(root, 'state', 'near_misses.json'));
  while (true) {
    if (file.existsSync()) {
      try {
        final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        final nearMisses = (json['near_misses'] as List<dynamic>)
            .map((nm) => NearMiss.fromJson(nm as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield nearMisses;
      } on FormatException {
        // skip
      }
    } else {
      yield [];
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
