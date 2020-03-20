(function() {
    window.makeFilter = function(filterItem, fieldDescriptions) {
	return function(item) {
	    var keep = true;
	    for (field in fieldDescriptions) {
		var fd = fieldDescriptions[field];
		if (filterItem[field] && (
		    !fd.hasOwnProperty("visible") || fd.visible)) {
		    if ((["number", "checkbox", "select"].indexOf(fd.type) > -1
			 && item[field] != filterItem[field]) ||
			(fd.type == "text" && 
			 item[field].toLowerCase().indexOf(
			     filterItem[field].toLowerCase()) == -1) ) {
			keep = false;
			break;
		    }
		}
	    };
	    return keep
	}
    };
    window.makeController = function(jsonURL, fieldDescriptions) {
	return {
	    loadData: function(filterItem) {
		var d = $.Deferred();
		$.ajax({url: jsonURL, dataType: "json"}).done(
		    function(loadData) {
			if (loadData.status != 0) {
			    $.notify(loadData.message);
			    d.resolve();
			} else { var items = loadData.data.filter(
			    makeFilter(filterItem, fieldDescriptions));
			       d.resolve(items) }
		    });
		return d.promise();
	    },	     
	    insertItem: function(item) {
		var d = $.Deferred();
		item.Id = 0;
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) { $.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	    updateItem: function(item) {
		var d = $.Deferred();
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) {$.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	    deleteItem: function(item) {
		var d = $.Deferred();
		if (item.Id) {item.Id = - item.Id};
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) { $.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	};
    };
})();
