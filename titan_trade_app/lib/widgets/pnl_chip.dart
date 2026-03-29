import 'package:flutter/material.dart';

import '../theme.dart';

class PnlChip extends StatelessWidget {
  final double value;
  final double? percent;

  const PnlChip({super.key, required this.value, this.percent});

  @override
  Widget build(BuildContext context) {
    final color = pnlColor(value);
    final sign = value >= 0 ? '+' : '';
    final label = percent != null
        ? '$sign\$${value.toStringAsFixed(2)} ($sign${percent!.toStringAsFixed(2)}%)'
        : '$sign\$${value.toStringAsFixed(2)}';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label, style: monoStyle.copyWith(color: color, fontSize: 13)),
    );
  }
}
