import 'package:flutter/material.dart';

class SentryBadge extends StatelessWidget {
  final String signal;

  const SentryBadge({super.key, required this.signal});

  @override
  Widget build(BuildContext context) {
    final isContinue = signal == 'CONTINUE';
    final color = isContinue ? Colors.green : Colors.red;
    final icon = isContinue ? Icons.check_circle : Icons.cancel;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(signal, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
