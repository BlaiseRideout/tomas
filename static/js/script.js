(function() {

	var selects = {},
		selectData = {};

	window.fillSelect = function(endpoint, selector, displayrow, valuerow, callback) {
		if (selects[endpoint] === undefined)
			$.getJSON(endpoint, function(data) {
				selects[endpoint] = document.createElement("select");
				selectData[endpoint] = data;
				for (var i = 0; i < data.length; ++i) {
					var option = document.createElement("option");
					$(option).text(data[i][displayrow]);
					$(option).val(data[i][valuerow]);
					selects[endpoint].appendChild(option);
				}
				fillSelect(endpoint, selector, displayrow, valuerow, callback);
			});
		else {
			$(selector).each(function(i, elem) {
				var select = selects[endpoint].cloneNode(true);
				select.className = this.className;
				$(select).val($(elem).data("value"));
				$(select).data("colname", $(elem).data("colname"));
				$(select).data("selectData", selectData[endpoint]);
				$(select).attr("name", $(elem).attr("name"));
				$(select).attr("form", $(elem).attr("form"));
				$(elem).replaceWith(select);
			});
			if (typeof callback === 'function')
				callback();
		}
	}

	window.xhrError = function(xhr, status, error) {
		console.log(status + ": " + error);
		console.log(xhr);
	}
})();
