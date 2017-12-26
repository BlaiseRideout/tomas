(function($) {
	$(function() {
		var players = null;

		var OTHERSTRING = "OTHER (PLEASE SPECIFY)";
		var SELECTSTRING = "PLEASE SELECT A PLAYER";
		var NEWPLAYERSTRING = "NEW PLAYER";

		function getPlayers() {
			$.getJSON('/seating/players.json', function(data) {
				players = data;
				populatePlayerComplete();
			}).fail(window.xhrError);
		}
		window.populatePlayerComplete = function(force) {
			if (players === null || force)
				return getPlayers();
			var elem = $("input.playercomplete");
			elem.autocomplete({
				source: players,
				minLength: 2
			});
			if (elem.next(".clearplayercomplete").length === 0) {
				elem.after("<button class=\"clearplayercomplete\">✖</button>");
				elem.each(function(_, complete) {
					$(complete).next(".clearplayercomplete").click(function(clearbutton) {
						$(complete).val("");
					});
				});
			}
		}

		window.xhrError = function(xhr, status, error) {
			console.log(status + ": " + error);
			console.log(xhr);
		}

    /* Names of endpoints that use javascript along with the empty string.
       These are removed from the end of URL lists to find the base URL.
     */
    window.tomas_component_names = [
	'', 'tournament', 'players', 'users', 'settings'
    ];
	    window.trimListR = function(list, trim_words, min_length) {
		/* Trim words from the right of list.  No list element can be
		   null.
		 */
		if (min_length == null) {
		    min_length = 0
		}
		var last = null, first = true;
		while (list.length > min_length && (
		    first || trim_words.indexOf(last) >= 0)) {
		    last = list.pop();
		    first = false;
		}
		if (last != null && trim_words.indexOf(last) < 0) {
		    list.push(last)
		}
		return list;
	    }
	});
})(jQuery);
